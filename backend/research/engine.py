"""Motor de backtest sin look-ahead y con costos pesimistas.

Reglas de ejecucion (identicas en backtest y paper trading):
  * La senal se calcula al CIERRE de la barra i.
  * La entrada ocurre en la APERTURA de la barra i+1, con slippage + medio spread en contra.
  * SL/TP se evaluan con high/low de cada barra. Si en una misma barra se tocan ambos, gana el SL (pesimista).
  * Si la apertura abre con gap mas alla del SL, se llena en la apertura (peor que el SL).
  * El SL (orden stop) paga el doble de slippage; el TP (limite) solo medio spread.
  * Fee por lado sobre el nocional. Salida por tiempo al cierre de la barra `max_hold`.
  * Una posicion a la vez por activo. Tamano = riesgo fijo % del equity a la distancia del SL, limitado a `max_lev`.
"""
from dataclasses import dataclass

import numpy as np

from .strategies import atr as atr_fn


@dataclass
class Costs:
    fee: float = 0.001        # 0.10% por lado (Binance spot sin descuento BNB)
    slippage: float = 0.0005  # 0.05% por lado
    spread: float = 0.0002    # 0.02% (se aplica medio spread por lado)


def simulate_trade(o, h, l, c, i, side, atr_i, sl_atr, tp_atr, max_hold, costs: Costs, force_close=True):
    """Simula UN trade con senal en el cierre de la barra i.

    Devuelve None si aun no existe la barra de entrada. status: 'closed' | 'open'
    ('open' solo si force_close=False y todavia no se resolvio).
    """
    n = len(o)
    e = i + 1
    if e >= n or not np.isfinite(atr_i) or atr_i <= 0:
        return None
    adverse = costs.slippage + costs.spread / 2
    entry = o[e] * (1 + side * adverse)
    sl = entry - side * sl_atr * atr_i
    tp = entry + side * tp_atr * atr_i
    last_allowed = e + max_hold - 1

    exit_px = reason = j_exit = None
    for j in range(e, min(last_allowed, n - 1) + 1):
        hit_sl = l[j] <= sl if side == 1 else h[j] >= sl
        hit_tp = h[j] >= tp if side == 1 else l[j] <= tp
        if hit_sl:  # pesimista: SL antes que TP si ambos caen en la misma barra
            base = min(o[j], sl) if side == 1 else max(o[j], sl)
            exit_px = base * (1 - side * (2 * costs.slippage + costs.spread / 2))
            reason, j_exit = "sl", j
            break
        if hit_tp:
            exit_px = tp * (1 - side * costs.spread / 2)
            reason, j_exit = "tp", j
            break
    if exit_px is None:
        if last_allowed <= n - 1:
            j_exit, reason = last_allowed, "time"
        elif force_close:
            j_exit, reason = n - 1, "end"
        else:
            return dict(status="open", side=side, signal_idx=i, entry_idx=e, entry=entry, sl=sl, tp=tp)
        exit_px = c[j_exit] * (1 - side * adverse)

    gross = side * (exit_px / entry - 1)
    net = gross - costs.fee * (1 + exit_px / entry)
    return dict(status="closed", side=side, signal_idx=i, entry_idx=e, exit_idx=j_exit, entry=entry,
                exit=exit_px, sl=sl, tp=tp, reason=reason, gross=gross, net=net,
                risk_frac=sl_atr * atr_i / entry)


def run_backtest(df, events, atr_arr, sl_atr, tp_atr, max_hold, costs=None, start=0, end=None,
                 shorts=False, risk_pct=0.01, max_lev=1.0):
    """Backtest sobre df[start:end]. Devuelve lista de trades con 'ret' = retorno sobre el equity."""
    costs = costs or Costs()
    end = len(df) if end is None else end
    o, h, l, c = (df[k].to_numpy()[:end] for k in ("open", "high", "low", "close"))
    ev = np.asarray(events)[:end]
    idx = df.index
    trades, free_from = [], start
    for i in np.flatnonzero(ev[start:end]) + start:
        side = int(ev[i])
        if i < free_from or (side == -1 and not shorts):
            continue
        t = simulate_trade(o, h, l, c, i, side, atr_arr[i], sl_atr, tp_atr, max_hold, costs, force_close=True)
        if t is None:
            continue
        frac = min(max_lev, risk_pct / t["risk_frac"])
        t["ret"] = frac * t["net"]
        t["frac"] = frac
        t["entry_time"], t["exit_time"] = idx[t["entry_idx"]], idx[t["exit_idx"]]
        trades.append(t)
        free_from = t["exit_idx"]
    return trades


def metrics(trades):
    """Metricas a nivel de trade (equity compuesto trade a trade)."""
    n = len(trades)
    if n == 0:
        return dict(n=0, ret_pct=0.0, win_rate=0.0, profit_factor=0.0, expectancy_pct=0.0,
                    max_dd_pct=0.0, tstat=0.0, sharpe=0.0)
    r = np.array([t["ret"] for t in trades])
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    dd = (eq / peak - 1).min()
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    sd = r.std(ddof=1) if n > 1 else 0.0
    tstat = r.mean() / (sd / np.sqrt(n)) if sd > 0 else 0.0
    span_days = max((trades[-1]["exit_time"] - trades[0]["entry_time"]).total_seconds() / 86400, 1)
    sharpe = (r.mean() / sd) * np.sqrt(n / span_days * 365) if sd > 0 else 0.0
    return dict(n=n, ret_pct=(eq[-1] - 1) * 100, win_rate=(r > 0).mean() * 100,
                profit_factor=(wins / losses) if losses > 0 else float("inf"),
                expectancy_pct=r.mean() * 100, max_dd_pct=dd * 100, tstat=tstat, sharpe=sharpe)


def bootstrap_pvalue(rets, n_boot=5000, seed=0):
    """P(media >= observada | H0: media verdadera = 0), remuestreando retornos centrados."""
    rets = np.asarray(rets, dtype=float)
    if len(rets) < 5:
        return 1.0
    rng = np.random.default_rng(seed)
    centered = rets - rets.mean()
    boots = rng.choice(centered, size=(n_boot, len(rets)), replace=True).mean(axis=1)
    return float((boots >= rets.mean()).mean())


def buy_and_hold_pct(df, start=0, end=None):
    end = len(df) if end is None else end
    return float((df["close"].iloc[end - 1] / df["open"].iloc[start] - 1) * 100)


def prep(df):
    return atr_fn(df, 14).to_numpy()
