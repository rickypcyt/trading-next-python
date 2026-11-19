"""
Dynamic Position Sizer - Ajusta automáticamente el capital asignado a cada engine
según su rendimiento histórico (win rate, profit factor, streak, P&L).

Engines con buen performance reciben más capital. Engines con mal performance
reciben menos. Esto simula un gestor de fondos que reasigna capital a los
estrategias ganadoras.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from database import Trade, EquityCurve
import threading


class EnginePerformance:
    """Métricas de rendimiento de un engine."""
    def __init__(self, engine_name: str):
        self.engine_name = engine_name
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.avg_win = 0.0
        self.avg_loss = 0.0
        self.win_rate = 0.0
        self.profit_factor = 0.0
        self.current_streak = 0  # Positivo = racha ganadora, negativo = perdedora
        self.last_trade_pnl = 0.0
        self.last_updated = datetime.min

    def update_from_trades(self, trades: list):
        """Recalcular métricas desde una lista de trades."""
        self.total_trades = len(trades)
        if self.total_trades == 0:
            return

        wins = [t for t in trades if (t.pnl or 0) > 0]
        losses = [t for t in trades if (t.pnl or 0) < 0]

        self.winning_trades = len(wins)
        self.losing_trades = len(losses)
        self.total_pnl = sum(t.pnl or 0 for t in trades)
        self.gross_profit = sum(t.pnl or 0 for t in wins)
        self.gross_loss = abs(sum(t.pnl or 0 for t in losses))

        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
        self.profit_factor = self.gross_profit / (self.gross_loss + 0.0001) if self.gross_loss > 0 else 999.0
        self.avg_win = self.gross_profit / self.winning_trades if self.winning_trades > 0 else 0.0
        self.avg_loss = self.gross_loss / self.losing_trades if self.losing_trades > 0 else 0.0

        # Calcular racha actual
        sorted_trades = sorted(trades, key=lambda t: t.timestamp_entry or datetime.min, reverse=True)
        streak = 0
        for t in sorted_trades:
            pnl = t.pnl or 0
            if pnl > 0:
                if streak >= 0:
                    streak += 1
                else:
                    break
            elif pnl < 0:
                if streak <= 0:
                    streak -= 1
                else:
                    break
            else:
                break
        self.current_streak = streak
        self.last_trade_pnl = sorted_trades[0].pnl if sorted_trades else 0.0
        self.last_updated = datetime.now()

    @property
    def is_profitable(self) -> bool:
        return self.total_pnl > 0 and self.win_rate >= 0.4

    @property
    def is_struggling(self) -> bool:
        return self.total_pnl < 0 or self.win_rate < 0.3


class DynamicPositionSizer:
    """
    Gestiona la asignación dinámica de capital entre engines.

    Reglas:
    - Capital base dividido equitativamente entre engines activos
    - Multiplicador de performance (0.5x - 3.0x) basado en win rate y profit factor
    - Bonus por racha ganadora, penalización por racha perdedora
    - Capital mínimo garantizado para que todos los engines puedan operar
    - Protección anti-ruina: si un engine pierde demasiado, se reduce su capital
    """

    def __init__(self, total_capital: float = 100.0):
        self.total_capital = total_capital
        self.base_allocation: Dict[str, float] = {}
        self.performance_multipliers: Dict[str, float] = {}
        self.final_allocations: Dict[str, float] = {}
        self.engine_performance: Dict[str, EnginePerformance] = {}
        self._lock = threading.Lock()
        self._last_refresh = datetime.min
        self._refresh_interval = timedelta(seconds=30)

    def _get_or_create_perf(self, engine_name: str) -> EnginePerformance:
        if engine_name not in self.engine_performance:
            self.engine_performance[engine_name] = EnginePerformance(engine_name)
        return self.engine_performance[engine_name]

    def refresh_from_db(self, db: Session, active_engines: Optional[list] = None):
        """
        Recalcular allocation desde la base de datos.
        Se llama periódicamente o después de cada trade.
        """
        with self._lock:
            now = datetime.now()
            if now - self._last_refresh < self._refresh_interval:
                return  # No refrescar demasiado frecuente

            # Obtener capital actual desde equity curve
            latest_equity = db.query(EquityCurve).order_by(
                EquityCurve.timestamp.desc()
            ).first()
            if latest_equity and latest_equity.capital:
                self.total_capital = latest_equity.capital

            # Obtener trades de las últimas 24h para evaluar performance
            cutoff = now - timedelta(hours=24)
            recent_trades = db.query(Trade).filter(
                Trade.timestamp_entry >= cutoff
            ).all()

            # Agrupar por engine
            engine_trades: Dict[str, list] = {}
            for trade in recent_trades:
                engine = trade.source_engine or self._infer_engine(trade.strategy or "")
                engine_trades.setdefault(engine, []).append(trade)

            # Si no hay engines activos especificados, usar los que tienen trades
            engines = active_engines or list(engine_trades.keys())
            if not engines:
                engines = ["binance_advanced", "intelligent", "micro_profit"]

            num_engines = len(engines)
            base_share = self.total_capital / num_engines if num_engines > 0 else 0

            self.base_allocation = {}
            self.performance_multipliers = {}
            self.final_allocations = {}

            for engine in engines:
                perf = self._get_or_create_perf(engine)
                trades_for_engine = engine_trades.get(engine, [])
                perf.update_from_trades(trades_for_engine)

                # Base allocation
                self.base_allocation[engine] = base_share

                # Performance multiplier (0.5x to 3.0x)
                multiplier = self._calculate_multiplier(perf)
                self.performance_multipliers[engine] = multiplier

                # Final allocation = base * multiplier, con límites
                raw_allocation = base_share * multiplier
                # Mínimo 10% del base, máximo 50% del capital total
                min_alloc = base_share * 0.1
                max_alloc = self.total_capital * 0.50
                final = max(min_alloc, min(raw_allocation, max_alloc))

                self.final_allocations[engine] = round(final, 2)

            # Normalizar para que la suma no exceda el capital total
            total_allocated = sum(self.final_allocations.values())
            if total_allocated > self.total_capital and total_allocated > 0:
                scale = self.total_capital / total_allocated
                for engine in self.final_allocations:
                    self.final_allocations[engine] = round(
                        self.final_allocations[engine] * scale, 2
                    )

            self._last_refresh = now

    def _calculate_multiplier(self, perf: EnginePerformance) -> float:
        """
        Calcular multiplicador de capital basado en performance.

        Factores:
        - Win rate: 40%+ es aceptable, 60%+ es excelente
        - Profit factor: >1.0 es rentable, >2.0 es excelente
        - Streak: racha ganadora aumenta, perdedora disminuye
        - Número mínimo de trades para evaluar (evitar ruido con pocos trades)
        """
        # Si hay menos de 5 trades, usar multiplicador neutral
        if perf.total_trades < 5:
            return 1.0

        multiplier = 1.0

        # Factor 1: Win rate
        # 0% win rate → 0.3x | 40% → 0.8x | 50% → 1.0x | 60% → 1.5x | 70%+ → 2.0x
        if perf.win_rate >= 0.70:
            multiplier *= 2.0
        elif perf.win_rate >= 0.60:
            multiplier *= 1.5
        elif perf.win_rate >= 0.50:
            multiplier *= 1.2
        elif perf.win_rate >= 0.40:
            multiplier *= 0.8
        else:
            multiplier *= 0.3

        # Factor 2: Profit factor
        # PF < 0.5 → 0.5x | PF 1.0 → 1.0x | PF 2.0 → 1.3x | PF 3.0+ → 1.5x
        if perf.profit_factor >= 3.0:
            multiplier *= 1.5
        elif perf.profit_factor >= 2.0:
            multiplier *= 1.3
        elif perf.profit_factor >= 1.0:
            multiplier *= 1.0
        elif perf.profit_factor >= 0.5:
            multiplier *= 0.7
        else:
            multiplier *= 0.4

        # Factor 3: Streak (racha)
        # Cada trade ganador consecutivo añade 5%, cada perdedor resta 10%
        if perf.current_streak > 0:
            streak_bonus = min(perf.current_streak * 0.05, 0.30)  # Máx +30%
            multiplier *= (1.0 + streak_bonus)
        elif perf.current_streak < 0:
            streak_penalty = min(abs(perf.current_streak) * 0.10, 0.50)  # Máx -50%
            multiplier *= (1.0 - streak_penalty)

        # Factor 4: P&L total positivo da bonus adicional
        if perf.total_pnl > 0:
            multiplier *= 1.1
        elif perf.total_pnl < -5.0:  # Pérdida significativa
            multiplier *= 0.6

        # Clamp final entre 0.2x y 3.0x
        return max(0.2, min(multiplier, 3.0))

    def _infer_engine(self, strategy: str) -> str:
        """Inferir engine desde el nombre de estrategia."""
        s = strategy.upper()
        if "ADV" in s or "MARKET_MAKING" in s:
            return "binance_advanced"
        if "MACD" in s or "MA_CROSS" in s or "RSI" in s or "BOLLINGER" in s:
            return "intelligent"
        if "MICRO" in s:
            return "micro_profit"
        if "MONTHLY" in s:
            return "monthly_target"
        return "unknown"

    def get_capital_for_engine(self, engine_name: str) -> float:
        """Obtener el capital asignado a un engine específico."""
        with self._lock:
            return self.final_allocations.get(engine_name, self.total_capital * 0.1)

    def get_risk_per_trade_for_engine(self, engine_name: str) -> float:
        """
        Obtener el riesgo por trade ajustado por performance.
        Engines con buen performance pueden arriesgar más.
        """
        with self._lock:
            multiplier = self.performance_multipliers.get(engine_name, 1.0)
            # Base 2%, ajustado por multiplier (0.5% a 5%)
            base_risk = 0.02
            adjusted = base_risk * multiplier
            return max(0.005, min(adjusted, 0.05))

    def get_allocation_summary(self) -> Dict:
        """Resumen completo de allocation para UI/API."""
        with self._lock:
            return {
                "total_capital": round(self.total_capital, 2),
                "allocations": {
                    engine: {
                        "base_allocation": round(self.base_allocation.get(engine, 0), 2),
                        "performance_multiplier": round(
                            self.performance_multipliers.get(engine, 1.0), 2
                        ),
                        "final_allocation": round(self.final_allocations.get(engine, 0), 2),
                        "win_rate": round(perf.win_rate, 4),
                        "profit_factor": round(perf.profit_factor, 2),
                        "total_trades": perf.total_trades,
                        "total_pnl": round(perf.total_pnl, 2),
                        "current_streak": perf.current_streak,
                        "risk_per_trade": round(
                            self.get_risk_per_trade_for_engine(engine), 4
                        ),
                    }
                    for engine, perf in self.engine_performance.items()
                },
                "last_refresh": self._last_refresh.isoformat() if self._last_updated else None,
            }

    def force_refresh(self):
        """Forzar refresh en la próxima llamada."""
        with self._lock:
            self._last_refresh = datetime.min


# Singleton global
dynamic_sizer = DynamicPositionSizer(total_capital=100.0)
