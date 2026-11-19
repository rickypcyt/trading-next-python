"""Estrategias CAUSALES: la señal en la barra i solo usa datos hasta el cierre de i.

Cada función devuelve una Serie de eventos: +1 entrada larga, -1 entrada corta, 0 nada.
La ejecución (entrada en la apertura de la barra siguiente, SL/TP, costos) vive en engine.py.
"""
import itertools

import numpy as np
import pandas as pd


# ---------- indicadores (Wilder donde corresponde) ----------
def sma(s, n):
    return s.rolling(n).mean()


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df, n=14):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _events(long_cond, short_cond):
    return (long_cond.fillna(False).astype(int) - short_cond.fillna(False).astype(int)).astype(int)


# ---------- estrategias ----------
def ma_cross(df, fast=10, slow=50):
    f, s = sma(df["close"], fast), sma(df["close"], slow)
    up = (f > s) & (f.shift() <= s.shift())
    dn = (f < s) & (f.shift() >= s.shift())
    return _events(up, dn)


def rsi_reversion(df, period=14, lo=30, hi=70):
    r = rsi(df["close"], period)
    return _events((r < lo) & (r.shift() >= lo), (r > hi) & (r.shift() <= hi))


def bollinger(df, period=20, k=2.0):
    m, sd = sma(df["close"], period), df["close"].rolling(period).std()
    lower, upper = m - k * sd, m + k * sd
    c = df["close"]
    return _events((c < lower) & (c.shift() >= lower.shift()), (c > upper) & (c.shift() <= upper.shift()))


def macd(df, fast=12, slow=26, signal=9):
    c = df["close"]
    line = c.ewm(span=fast, adjust=False).mean() - c.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    return _events((line > sig) & (line.shift() <= sig.shift()), (line < sig) & (line.shift() >= sig.shift()))


def volume_breakout(df, lookback=20, vol_mult=1.5):
    hh = df["high"].rolling(lookback).max().shift()
    ll = df["low"].rolling(lookback).min().shift()
    vr = df["volume"] / df["volume"].rolling(lookback).mean()
    return _events((df["close"] > hh) & (vr > vol_mult), (df["close"] < ll) & (vr > vol_mult))


EXIT_GRID = {"sl_atr": [1.5, 2.5], "tp_atr": [2.0, 4.0], "max_hold": [24, 72]}
EXIT_DEFAULT = {"sl_atr": 2.0, "tp_atr": 3.0, "max_hold": 48}

# nombre -> (función, parámetros por defecto de señal, grilla de señal)
STRATEGIES = {
    "MA_Cross": (ma_cross, {"fast": 10, "slow": 50}, {"fast": [5, 10, 20], "slow": [30, 50, 100]}),
    "RSI_Reversion": (rsi_reversion, {"period": 14, "lo": 30, "hi": 70}, {"period": [7, 14], "lo": [20, 30], "hi": [70, 80]}),
    "Bollinger": (bollinger, {"period": 20, "k": 2.0}, {"period": [20, 40], "k": [2.0, 2.5, 3.0]}),
    "MACD": (macd, {"fast": 12, "slow": 26, "signal": 9}, {"fast": [8, 12], "slow": [21, 26], "signal": [9]}),
    "Volume_Breakout": (volume_breakout, {"lookback": 20, "vol_mult": 1.5}, {"lookback": [20, 50], "vol_mult": [1.5, 2.0]}),
}


def grid_combos(grid):
    keys = list(grid)
    return [dict(zip(keys, v)) for v in itertools.product(*grid.values())]
