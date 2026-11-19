import random
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from database import Trade, EquityCurve, Metric, Alert
from decision_engine import DecisionEngine, decision_engine as default_decision_engine
from execution_engine import execution_engine, TradeRequest, TradeDirection
from simulator import TradingSimulator


class UnifiedStrategyEngine:
    """Unified engine: context -> regime -> decision -> execution -> database."""

    def __init__(
        self,
        decision_engine: Optional[DecisionEngine] = None,
    ):
        self.decision_engine = decision_engine or default_decision_engine

    async def analyze(self, symbol: str) -> Dict:
        """Analyze market and return decision without trading."""
        return await self.decision_engine.analyze(symbol)

    async def generate_trade(self, db: Session, symbol: str, capital: float, risk_per_trade: float = 0.02) -> Optional[Dict]:
        """Run full pipeline and generate a trade if the decision allows it."""
        analysis = await self.analyze(symbol)
        if "error" in analysis:
            return {"status": "error", "message": analysis["error"]}

        decision = analysis["decision"]
        direction = analysis["direction"]

        if direction not in ("LONG", "SHORT"):
            return {
                "status": "skipped",
                "decision": decision,
                "score": analysis["score"],
                "reason": "El motor decidió no operar.",
                "analysis": self._analysis_without_context(analysis),
            }

        current_price = analysis.get("current_price", 0.0)
        if current_price <= 0:
            return {"status": "error", "message": "Precio actual no disponible"}

        # Use 1h/24h context for ATR, support, resistance and volatility
        context = analysis.get("context", {})
        summary = context.get("summary", {})
        timeframes = context.get("timeframes", {})
        tf_current = timeframes.get("1h") or timeframes.get("24h")

        atr_pct = tf_current.get("atr_pct", 0.0) if tf_current else 0.0
        volatility = summary.get("volatilidad", 2.0) or 2.0
        support = summary.get("soporte", current_price * 0.98) or current_price * 0.98
        resistance = summary.get("resistencia", current_price * 1.02) or current_price * 1.02

        # Build stop and target around ATR and support/resistance
        multiplier = 1.5
        if direction == "LONG":
            stop_loss = max(
                support * 0.995,
                current_price * (1 - (atr_pct * multiplier / 100)),
            )
            take_profit = min(
                resistance * 0.995,
                current_price * (1 + (atr_pct * multiplier * 2 / 100)),
            )
        else:
            stop_loss = min(
                resistance * 1.005,
                current_price * (1 + (atr_pct * multiplier / 100)),
            )
            take_profit = max(
                support * 1.005,
                current_price * (1 - (atr_pct * multiplier * 2 / 100)),
            )

        trade_request = TradeRequest(
            symbol=symbol.upper(),
            direction=TradeDirection.LONG if direction == "LONG" else TradeDirection.SHORT,
            entry_price=current_price,
            size=0.0,  # Execution engine will size based on risk
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=analysis["recommended_strategy"],
            volatility=volatility,
        )

        # Open trade
        open_result = execution_engine.execute_trade(trade_request, capital, risk_per_trade)
        if open_result.position_size <= 0:
            return {"status": "error", "message": "Tamaño de posición calculado en cero"}

        # Simulate exit based on the decision score
        win_probability = min(analysis["score"] / 100.0, 0.95)
        if random.random() < win_probability:
            exit_price = take_profit
            exit_reason = "take_profit"
        else:
            exit_price = stop_loss
            exit_reason = "stop_loss"

        closed_trade = execution_engine.close_trade(
            open_result,
            exit_price,
            exit_reason,
            volatility,
        )

        # Persist as Trade
        duration_ms = int(
            (closed_trade.timestamp_exit - closed_trade.timestamp_entry).total_seconds() * 1000
        )
        trade = Trade(
            timestamp_entry=closed_trade.timestamp_entry,
            timestamp_exit=closed_trade.timestamp_exit,
            symbol=closed_trade.symbol,
            strategy=f"{analysis['recommended_strategy']}",
            entry_price=round(closed_trade.actual_entry_price, 6),
            exit_price=round(closed_trade.actual_exit_price, 6),
            requested_entry_price=round(closed_trade.requested_entry_price, 6),
            requested_exit_price=round(closed_trade.requested_exit_price, 6) if closed_trade.requested_exit_price else None,
            size=round(closed_trade.position_size, 8),
            pnl=round(closed_trade.net_pnl, 6),
            gross_pnl=round(closed_trade.gross_pnl, 6),
            entry_fees=round(closed_trade.entry_fees, 6),
            exit_fees=round(closed_trade.exit_fees, 6),
            slippage_cost=round(closed_trade.slippage_cost, 6),
            spread_cost=round(closed_trade.spread_cost, 6),
            total_costs=round(
                closed_trade.entry_fees + closed_trade.exit_fees + closed_trade.slippage_cost + closed_trade.spread_cost, 6
            ),
            stop_loss=round(stop_loss, 6),
            take_profit=round(take_profit, 6),
            confidence=round(analysis["score"] / 100, 3),
            volatility=round(volatility, 2),
            source_engine="strategy_engine",
            source_mode=analysis["regime"].get("regime", "SIDEWAYS"),
            direction=closed_trade.direction.value,
            duration_ms=duration_ms,
            entry_reason=f"score:{analysis['score']}|{analysis['recommended_strategy']}",
            exit_reason=exit_reason,
            status="executed",
        )

        db.add(trade)
        db.commit()
        db.refresh(trade)

        # Update equity and metrics using the existing simulator helpers
        new_capital = capital + trade.pnl
        equity = EquityCurve(
            timestamp=datetime.utcnow(),
            capital=round(new_capital, 2),
        )
        db.merge(equity)
        db.commit()
        db.refresh(equity)

        sim = TradingSimulator(db)
        sim.current_capital = new_capital
        sim.max_capital = max(new_capital, capital)
        metrics = sim.calculate_metrics()
        if metrics:
            db.add(metrics)
            db.commit()
            db.refresh(metrics)

        alerts = sim.check_alerts(trade)
        for alert in alerts:
            db.add(alert)
        if alerts:
            db.commit()
            for alert in alerts:
                db.refresh(alert)

        return {
            "status": "executed",
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "decision": decision,
            "score": analysis["score"],
            "probability": analysis["probability"],
            "pnl": trade.pnl,
            "capital": new_capital,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "size": trade.size,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "regime": analysis["regime"]["regime"],
            "strategy": trade.strategy,
            "risk": analysis["risk"],
            "analysis": self._analysis_without_context(analysis),
        }

    def _analysis_without_context(self, analysis: Dict) -> Dict:
        """Return a smaller version of the analysis without the DataFrame-backed context."""
        return {
            "symbol": analysis.get("symbol"),
            "current_price": analysis.get("current_price"),
            "score": analysis.get("score"),
            "probability": analysis.get("probability"),
            "decision": analysis.get("decision"),
            "risk": analysis.get("risk"),
            "direction": analysis.get("direction"),
            "recommended_strategy": analysis.get("recommended_strategy"),
            "regime": analysis.get("regime"),
            "summary": analysis.get("summary"),
            "factors": analysis.get("factors"),
        }


# Global instance
strategy_engine = UnifiedStrategyEngine()
