import numpy as np
import pandas as pd

from research.paper_trader import new_bot, step_bot


def make_df(closes, lows=None, highs=None):
    closes = np.array(closes, dtype=float)
    return pd.DataFrame(
        {"open": closes, "high": highs if highs is not None else closes + 0.5,
         "low": lows if lows is not None else closes - 0.5, "close": closes, "volume": 1.0},
        index=pd.date_range("2024-01-01", periods=len(closes), freq="h", tz="UTC"))


def test_starts_live_without_backfilling_history():
    rng = np.random.default_rng(3)
    df = make_df(100 + rng.normal(0, 1, 300).cumsum())
    bot = new_bot(df)
    assert step_bot(bot, df, "MA_Cross") == []  # no reproduce senales viejas
    assert bot["position"] is None and bot["trades"] == []


def test_state_is_resumable_and_closed_trade_is_booked_once():
    # tendencia plana, cruce alcista justo en la ultima vela -> posicion pendiente; luego sube y toca TP
    base = [100.0] * 80
    flat = make_df(base)
    bot = new_bot(flat)
    ups = np.concatenate([base, np.linspace(100, 140, 60)])
    df2 = make_df(ups, highs=ups + 0.5, lows=ups - 0.5)
    bot["search_from"] = str(df2.index[79])  # permite la senal desde el inicio del tramo alcista
    first = step_bot(bot, df2.iloc[:100], "MA_Cross")
    rest = step_bot(bot, df2, "MA_Cross")
    all_trades = first + rest
    assert len(bot["trades"]) == len(all_trades)
    assert len({t["signal_time"] for t in bot["trades"]}) == len(bot["trades"])  # sin duplicados
