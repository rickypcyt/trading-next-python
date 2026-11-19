import numpy as np
import pandas as pd
import pytest

from research.engine import Costs, metrics, run_backtest, simulate_trade
from research.strategies import ma_cross

ZERO = Costs(fee=0.0, slippage=0.0, spread=0.0)


def arrays(o, h, l, c):
    return [np.array(x, dtype=float) for x in (o, h, l, c)]


def test_entry_is_next_bar_open_not_signal_close():
    o, h, l, c = arrays([100, 110, 110, 110], [100, 111, 111, 111], [100, 109, 109, 109], [100, 110, 110, 110])
    t = simulate_trade(o, h, l, c, 0, 1, 2.0, 50, 50, 2, ZERO)
    assert t["entry_idx"] == 1 and t["entry"] == 110  # abre en o[1], no en c[0]=100


def test_sl_wins_when_sl_and_tp_hit_same_bar():
    o, h, l, c = arrays([100, 100, 100], [100, 100, 120], [100, 100, 80], [100, 100, 100])
    t = simulate_trade(o, h, l, c, 0, 1, 5.0, 2.0, 2.0, 5, ZERO)  # SL=90, TP=110; barra 2 toca ambos
    assert t["entry_idx"] == 1 and t["reason"] == "sl" and t["net"] < 0


def test_gap_through_stop_fills_at_open():
    o, h, l, c = arrays([100, 100, 80], [100, 100, 81], [100, 100, 79], [100, 100, 80])
    t = simulate_trade(o, h, l, c, 0, 1, 5.0, 2.0, 4.0, 5, ZERO)  # SL=90, la barra 2 abre en 80
    assert t["reason"] == "sl" and t["exit"] == 80


def test_costs_make_flat_trade_lose_money():
    n = 10
    flat = [100.0] * n
    o, h, l, c = arrays(flat, flat, flat, flat)
    t = simulate_trade(o, h, l, c, 0, 1, 1.0, 5.0, 5.0, 3, Costs())
    assert t["reason"] == "time" and t["net"] < -0.002  # fees + slippage + spread > 0.2% ida y vuelta


def test_open_trade_reported_when_not_forced():
    o, h, l, c = arrays([100] * 4, [100] * 4, [100] * 4, [100] * 4)
    t = simulate_trade(o, h, l, c, 0, 1, 1.0, 5.0, 5.0, 50, ZERO, force_close=False)
    assert t["status"] == "open"


def test_signals_are_causal():
    """Cambiar el futuro no debe cambiar las senales pasadas."""
    rng = np.random.default_rng(1)
    close = pd.Series(100 + rng.normal(0, 1, 400).cumsum())
    df = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0})
    full = ma_cross(df, 5, 20)
    cut = ma_cross(df.iloc[:300], 5, 20)
    assert (full.iloc[:300].to_numpy() == cut.to_numpy()).all()
    mutated = df.copy()
    mutated.loc[300:, "close"] += 50
    assert (ma_cross(mutated, 5, 20).iloc[:300].to_numpy() == cut.to_numpy()).all()


def test_no_trades_overlap_and_metrics_basic():
    rng = np.random.default_rng(2)
    close = 100 + rng.normal(0, 1, 600).cumsum()
    df = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0},
                      index=pd.date_range("2024-01-01", periods=600, freq="h", tz="UTC"))
    ev = ma_cross(df, 5, 20).to_numpy()
    atr_arr = (df["high"] - df["low"]).rolling(14).mean().to_numpy()
    tr = run_backtest(df, ev, atr_arr, 2.0, 3.0, 24, shorts=True)
    assert all(a["exit_idx"] <= b["signal_idx"] for a, b in zip(tr, tr[1:]))
    assert metrics(tr)["n"] == len(tr)
    assert metrics([])["n"] == 0
