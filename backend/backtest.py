"""
Backtest rápido sobre datos históricos de Binance.

Genera miles de trades simulados en minutos usando el mismo motor de estrategias
avanzadas y el execution_engine del sistema, sin depender del tiempo real.
"""
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from binance.client import Client

from advanced_strategies import (
    AdvancedStrategyEngine,
    MarketMakingOrder,
    OrderSide,
    RiskLevel,
    StrategyType,
)
from execution_engine import (
    ExecutionEngine,
    TradeDirection,
    TradeRequest,
    TradeResult,
)
from risk_settings import RISK_LEVEL


def get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def load_config() -> dict:
    symbols_raw = get_env("BACKTEST_SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,ADAUSDT,SOLUSDT,XRPUSDT")
    return {
        "symbols": [s.strip().upper() for s in symbols_raw.split(",") if s.strip()],
        "interval": get_env("BACKTEST_INTERVAL", "1h"),
        "lookback_days": int(get_env("BACKTEST_LOOKBACK_DAYS", "60")),
        "risk_level": get_env("BACKTEST_RISK_LEVEL", RISK_LEVEL).upper(),
        "capital": float(get_env("BACKTEST_CAPITAL", "100.0")),
        "leverage": float(get_env("BACKTEST_LEVERAGE", "1.0")),
        "output": get_env("BACKTEST_OUTPUT", "backtest_results.json"),
        "max_hold_bars": int(get_env("BACKTEST_MAX_HOLD_BARS", "3")),
    }


def calculate_volatility(prices: List[float], window: int = 24) -> float:
    """Estimación simple de volatilidad como media de retornos absolutos."""
    if len(prices) < 2:
        return 0.02
    recent = prices[-window:] if len(prices) >= window else prices
    returns = [(recent[i] - recent[i - 1]) / recent[i - 1] for i in range(1, len(recent))]
    if not returns:
        return 0.02
    return max(np.mean(np.abs(returns)), 0.0001)


def parse_risk_level(value: str) -> RiskLevel:
    try:
        return RiskLevel[value]
    except KeyError:
        return RiskLevel.MODERATE


@dataclass
class BacktestTrade:
    symbol: str
    strategy: str
    direction: str
    entry_price: float
    exit_price: float
    size: float
    entry_time: datetime
    exit_time: datetime
    net_pnl: float
    pnl_pct: float
    confidence: float


def map_side(side: OrderSide) -> TradeDirection:
    return TradeDirection.LONG if side == OrderSide.BUY else TradeDirection.SHORT


def build_trade_request(
    signal: MarketMakingOrder, symbol: str, volatility: float
) -> TradeRequest:
    direction = map_side(signal.side)
    price = signal.price

    if signal.stop_loss and signal.target_profit:
        if direction == TradeDirection.LONG:
            stop_loss = signal.stop_loss
            take_profit = signal.target_profit
        else:
            stop_loss = signal.target_profit
            take_profit = signal.stop_loss
    else:
        stop_distance = max(0.005, volatility * 0.3)
        if direction == TradeDirection.LONG:
            stop_loss = price * (1 - stop_distance)
            take_profit = price * (1 + volatility * 0.8)
        else:
            stop_loss = price * (1 + stop_distance)
            take_profit = price * (1 - volatility * 0.8)

    return TradeRequest(
        symbol=symbol,
        direction=direction,
        entry_price=price,
        size=signal.size,
        stop_loss=stop_loss,
        take_profit=take_profit,
        strategy=f"ADV_{signal.strategy.value.upper()}_{signal.side.name}",
        volatility=volatility * 100,
    )


def close_at_next_candle(
    engine: ExecutionEngine,
    open_trade: TradeResult,
    exit_price: float,
    exit_time: datetime,
    volatility: float,
) -> TradeResult:
    return engine.close_trade(
        open_trade,
        exit_price,
        exit_reason="next_candle_close",
        volatility=volatility * 100,
    )


def resolve_exit(
    df: pd.DataFrame,
    entry_index: int,
    direction: TradeDirection,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    max_bars: int,
) -> tuple[float, datetime, int, str]:
    """Busca salida por SL/TP dentro de las siguientes velas, o cierra al final."""
    end_index = min(entry_index + max_bars, len(df) - 1)
    for j in range(entry_index + 1, end_index + 1):
        row = df.iloc[j]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        exit_time = row["open_time"].to_pydatetime().replace(tzinfo=None)

        if direction == TradeDirection.LONG:
            if high >= take_profit:
                return take_profit, exit_time, j, "take_profit"
            if low <= stop_loss:
                return stop_loss, exit_time, j, "stop_loss"
        else:
            if low <= take_profit:
                return take_profit, exit_time, j, "take_profit"
            if high >= stop_loss:
                return stop_loss, exit_time, j, "stop_loss"

    # Sin disparo: cerrar al cierre de la última vela del hold
    row = df.iloc[end_index]
    return (
        float(row["close"]),
        row["open_time"].to_pydatetime().replace(tzinfo=None),
        end_index,
        "max_hold_close",
    )


async def fetch_klines(client: Client, symbol: str, interval: str, days: int) -> pd.DataFrame:
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    klines = await asyncio.to_thread(
        client.get_historical_klines,
        symbol=symbol,
        interval=interval,
        start_str=start_ms,
        end_str=end_ms,
        limit=1000,
    )

    if not klines:
        return pd.DataFrame()

    df = pd.DataFrame(
        klines,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ],
    )
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df = df.sort_values("open_time").reset_index(drop=True)
    return df


def run_symbol_backtest(
    df: pd.DataFrame,
    symbol: str,
    risk_level: RiskLevel,
    start_capital: float,
    leverage: float,
    max_hold_bars: int,
) -> tuple[List[BacktestTrade], float]:
    engine = ExecutionEngine()
    strategy_engine = AdvancedStrategyEngine(
        symbol=symbol,
        current_price=float(df["close"].iloc[0]),
        volatility=0.02,
        risk_level=risk_level,
        capital=start_capital,
        leverage=leverage,
    )

    trades: List[BacktestTrade] = []
    capital = start_capital
    prices_history: List[float] = []

    for i in range(len(df)):
        row = df.iloc[i]
        timestamp = row["open_time"].to_pydatetime().replace(tzinfo=None)
        close = float(row["close"])
        prices_history.append(close)

        volatility = calculate_volatility(prices_history, window=24)
        strategy_engine.current_price = close
        strategy_engine.volatility = volatility
        strategy_engine.capital = capital
        strategy_engine.update_price(close, timestamp=timestamp)

        signals = strategy_engine.get_all_strategy_signals()
        if not signals:
            continue

        # Tomar la mejor señal (mayor confianza)
        best_signal = signals[0]

        # Ejecutar entrada
        trade_request = build_trade_request(best_signal, symbol, volatility)
        open_trade = engine.execute_trade(trade_request, capital, risk_per_trade=0.02)

        if open_trade.position_size <= 0:
            continue

        # Resolver salida considerando SL/TP dentro de las siguientes velas
        exit_price, exit_time, _, exit_reason = resolve_exit(
            df,
            i,
            trade_request.direction,
            trade_request.entry_price,
            trade_request.stop_loss or (trade_request.entry_price * 0.99),
            trade_request.take_profit or (trade_request.entry_price * 1.01),
            max_hold_bars,
        )

        closed_trade = engine.close_trade(
            open_trade,
            exit_price,
            exit_reason=exit_reason,
            volatility=volatility * 100,
        )

        capital += closed_trade.net_pnl
        if capital <= 0:
            capital = 0.01

        trades.append(
            BacktestTrade(
                symbol=symbol,
                strategy=closed_trade.strategy,
                direction=closed_trade.direction.value,
                entry_price=round(closed_trade.actual_entry_price, 4),
                exit_price=round(closed_trade.actual_exit_price, 4),
                size=round(closed_trade.position_size, 6),
                entry_time=open_trade.timestamp_entry,
                exit_time=closed_trade.timestamp_exit or exit_time,
                net_pnl=round(closed_trade.net_pnl, 4),
                pnl_pct=round(closed_trade.pnl_percentage, 4),
                confidence=round(best_signal.confidence, 2),
            )
        )

    return trades, capital


def compute_metrics(trades: List[BacktestTrade], start_capital: float) -> Dict:
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "return_pct": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "max_drawdown_pct": 0.0,
            "final_capital": start_capital,
        }

    pnls = [t.net_pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_pnl = sum(pnls)
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0.0
    profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else (
        float("inf") if wins else 0.0
    )

    running = start_capital
    max_capital = start_capital
    max_dd = 0.0
    for p in pnls:
        running += p
        max_capital = max(max_capital, running)
        dd = (max_capital - running) / max_capital
        max_dd = max(max_dd, dd)

    return {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 4),
        "return_pct": round((total_pnl / start_capital) * 100, 4),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "avg_win": round(np.mean(wins), 4) if wins else 0.0,
        "avg_loss": round(np.mean(losses), 4) if losses else 0.0,
        "max_drawdown_pct": round(max_dd * 100, 4),
        "final_capital": round(start_capital + total_pnl, 4),
    }


async def main():
    config = load_config()
    print("⚙️ Configuración:")
    for k, v in config.items():
        print(f"  {k}: {v}")

    client = Client()  # Datos públicos

    risk_level = parse_risk_level(config["risk_level"])
    all_trades: List[BacktestTrade] = []
    per_symbol_metrics: Dict[str, Dict] = {}

    for symbol in config["symbols"]:
        print(f"\n📥 Descargando datos históricos para {symbol}...")
        df = await fetch_klines(client, symbol, config["interval"], config["lookback_days"])
        if df.empty:
            print(f"  ⚠️ No se pudieron obtener datos para {symbol}")
            continue
        print(f"  {len(df)} velas descargadas")

        trades, final_capital = run_symbol_backtest(
            df,
            symbol,
            risk_level,
            config["capital"],
            config["leverage"],
            config["max_hold_bars"],
        )
        metrics = compute_metrics(trades, config["capital"])
        per_symbol_metrics[symbol] = metrics
        all_trades.extend(trades)

        print(f"  Trades: {metrics['total_trades']} | Win rate: {metrics['win_rate']}% | "
              f"P&L: ${metrics['total_pnl']:.2f} | Return: {metrics['return_pct']}% | "
              f"Max DD: {metrics['max_drawdown_pct']}%")

    global_metrics = compute_metrics(all_trades, config["capital"] * len(config["symbols"]))

    print("\n" + "=" * 60)
    print("RESULTADOS GLOBALES")
    print("=" * 60)
    print(f"Total trades: {global_metrics['total_trades']}")
    print(f"Win rate: {global_metrics['win_rate']}%")
    print(f"Profit factor: {global_metrics['profit_factor']}")
    print(f"P&L total: ${global_metrics['total_pnl']:.2f}")
    print(f"Retorno: {global_metrics['return_pct']}%")
    print(f"Max drawdown: {global_metrics['max_drawdown_pct']}%")
    print(f"Capital final: ${global_metrics['final_capital']:.2f}")
    print("=" * 60)

    # Guardar resultados
    import json
    results = {
        "config": config,
        "summary": global_metrics,
        "per_symbol": per_symbol_metrics,
        "trades": [t.__dict__ for t in all_trades],
    }
    with open(config["output"], "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Resultados guardados en {config['output']}")


if __name__ == "__main__":
    asyncio.run(main())
