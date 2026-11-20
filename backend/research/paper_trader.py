"""Paper trading en vivo con precios REALES de Binance (sin dinero, sin random).

Usa exactamente el mismo motor/costos que el backtest, asi se puede comparar paper vs backtest.
Cada ejecucion procesa las velas cerradas nuevas y guarda el estado en research/results/paper_state.json.

Uso (desde backend/):
  python -m research.paper_trader            # una pasada (ideal para cron / Task Scheduler cada hora)
  python -m research.paper_trader --loop     # corre para siempre, una pasada por vela de 1h
  python -m research.paper_trader --status   # resumen
  python -m research.paper_trader --reset    # borra el estado

Kill switch: si el equity de un bot cae mas de MAX_DD_HALT desde su maximo, deja de abrir trades.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .data import load_klines
from .engine import Costs, prep, simulate_trade
from .strategies import EXIT_DEFAULT, STRATEGIES

STATE_PATH = Path(__file__).parent / "results" / "paper_state.json"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"]
START_EQUITY = 1000.0
RISK_PCT = 0.01
MAX_DD_HALT = 0.15
HISTORY_DAYS = 60


def new_bot(df):
    # La primera senal valida es la de la ultima vela cerrada: arrancamos "en vivo", sin backfill historico.
    return dict(equity=START_EQUITY, peak=START_EQUITY, halted=False, position=None,
                search_from=str(df.index[-1]), trades=[])


def step_bot(bot, df, strat_name, costs=None, shorts=False, params=None, exits=None):
    """Procesa las velas cerradas de `df` para un bot. Funcion pura sobre (bot, df): facil de testear."""
    costs = costs or Costs()
    func, defaults, _ = STRATEGIES[strat_name]
    ex = {**EXIT_DEFAULT, **(exits or {})}
    events = func(df, **{**defaults, **(params or {})}).to_numpy()
    atr_arr = prep(df)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    times = df.index
    booked = []

    def idx_of(ts):
        return int(times.searchsorted(pd.Timestamp(ts)))

    pos = bot["position"]
    search = idx_of(bot["search_from"])
    while True:
        if pos is None:
            if bot["halted"]:
                search = len(df)
                break
            cand = [i for i in np.flatnonzero(events[search:]) + search if shorts or events[i] == 1]
            if not cand:
                search = len(df)
                break
            i = int(cand[0])
            pos = dict(signal_time=str(times[i]), side=int(events[i]))
        i = idx_of(pos["signal_time"])
        t = simulate_trade(o, h, l, c, i, pos["side"], atr_arr[i], ex["sl_atr"], ex["tp_atr"],
                           ex["max_hold"], costs, force_close=False)
        if t is None or t["status"] == "open":
            bot["position"] = pos
            break
        frac = min(1.0, RISK_PCT / t["risk_frac"])
        ret = frac * t["net"]
        pnl = bot["equity"] * ret
        bot["equity"] *= 1 + ret
        bot["peak"] = max(bot["peak"], bot["equity"])
        rec = dict(strategy=strat_name, side="long" if t["side"] == 1 else "short",
                   signal_time=pos["signal_time"], entry_time=str(times[t["entry_idx"]]),
                   exit_time=str(times[t["exit_idx"]]), entry=round(t["entry"], 6), exit=round(t["exit"], 6),
                   reason=t["reason"], ret_pct=round(ret * 100, 4), pnl=round(pnl, 4),
                   equity=round(bot["equity"], 4))
        bot["trades"].append(rec)
        booked.append(rec)
        if bot["equity"] < bot["peak"] * (1 - MAX_DD_HALT):
            bot["halted"] = True
        pos = None
        search = int(t["exit_idx"])  # backtest: nueva senal permitida desde la barra de salida

    if pos is None:
        bot["position"] = None
        bot["search_from"] = str(times[-1] + (times[-1] - times[-2]))  # proxima vela aun no cerrada
    return booked


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return dict(created=datetime.now(timezone.utc).isoformat(), bots={})


def save_state(state):
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1))


def run_once(shorts=False):
    state = load_state()
    n_new = 0
    for sym in SYMBOLS:
        df = load_klines(sym, "1h", HISTORY_DAYS)
        for name in STRATEGIES:
            key = f"{sym}|{name}"
            bot = state["bots"].setdefault(key, new_bot(df))
            for rec in step_bot(bot, df, name, shorts=shorts):
                n_new += 1
                print(f"[{rec['exit_time']}] {key} {rec['side']} {rec['reason']} {rec['ret_pct']:+.2f}% -> equity {rec['equity']:.2f}")
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print(f"Pasada completa. Trades nuevos: {n_new}")


def status():
    state = load_state()
    if not state["bots"]:
        print("Sin estado todavia. Ejecuta una pasada primero.")
        return
    print(f"{'bot':26} {'trades':>6} {'win%':>6} {'equity':>9} {'ret%':>7} {'pos':>6} {'halt':>5}")
    tot, n_all = 0.0, 0
    for k, b in sorted(state["bots"].items()):
        tr = b["trades"]
        wr = 100 * np.mean([t["pnl"] > 0 for t in tr]) if tr else 0
        tot += b["equity"] - START_EQUITY
        n_all += len(tr)
        print(f"{k:26} {len(tr):6d} {wr:6.1f} {b['equity']:9.2f} {(b['equity']/START_EQUITY-1)*100:7.2f} "
              f"{'open' if b['position'] else '-':>6} {'YES' if b['halted'] else '':>5}")
    print(f"\nPnL total de todos los bots: {tot:+.2f} sobre {START_EQUITY * len(state['bots']):.0f} virtuales; trades: {n_all}")
    print("Con <100 trades por bot NO hay evidencia estadistica; deja correr semanas.")


def loop(shorts=False):
    while True:
        run_once(shorts)
        now = time.time()
        wait = 3600 - (now % 3600) + 20  # 20s despues del cierre de la siguiente vela
        print(f"Durmiendo {wait/60:.1f} min...")
        time.sleep(wait)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--shorts", action="store_true")
    a = ap.parse_args()
    if a.reset:
        STATE_PATH.unlink(missing_ok=True)
        print("Estado borrado.")
    elif a.status:
        status()
    elif a.loop:
        loop(a.shorts)
    else:
        run_once(a.shorts)


if __name__ == "__main__":
    main()
