"""Walk-forward: optimiza en una ventana de entrenamiento y evalua SOLO en la ventana siguiente (fuera de muestra)."""
from .engine import Costs, bootstrap_pvalue, buy_and_hold_pct, metrics, prep, run_backtest
from .strategies import EXIT_GRID, STRATEGIES, grid_combos


def walk_forward(df, strat_name, costs=None, train_days=180, test_days=60, min_trades=20,
                 shorts=False, interval_hours=1, risk_pct=0.01):
    costs = costs or Costs()
    func, _, sig_grid = STRATEGIES[strat_name]
    atr_arr = prep(df)
    train_bars = int(train_days * 24 / interval_hours)
    test_bars = int(test_days * 24 / interval_hours)
    exit_combos = grid_combos(EXIT_GRID)
    events_cache = [(p, func(df, **p).to_numpy()) for p in grid_combos(sig_grid)]

    windows, oos_trades = [], []
    start = train_bars
    while start + test_bars <= len(df):
        tr_lo, tr_hi, te_hi = start - train_bars, start, start + test_bars
        best = None
        for sp, ev in events_cache:
            for ep in exit_combos:
                trades = run_backtest(df, ev, atr_arr, costs=costs, start=tr_lo, end=tr_hi,
                                      shorts=shorts, risk_pct=risk_pct, **ep)
                if len(trades) < min_trades:
                    continue
                m = metrics(trades)
                if m["tstat"] > 0 and (best is None or m["tstat"] > best[0]):
                    best = (m["tstat"], sp, ep, ev)
        w = dict(train_start=str(df.index[tr_lo]), test_start=str(df.index[tr_hi]), test_end=str(df.index[te_hi - 1]))
        if best is None:
            w.update(chosen=None, oos=metrics([]), is_tstat=0.0)  # sin edge en train -> cash
        else:
            tstat_is, sp, ep, ev = best
            t = run_backtest(df, ev, atr_arr, costs=costs, start=tr_hi, end=te_hi,
                             shorts=shorts, risk_pct=risk_pct, **ep)
            oos_trades += t
            w.update(chosen={**sp, **ep}, is_tstat=tstat_is, oos=metrics(t))
        windows.append(w)
        start += test_bars

    oos_trades.sort(key=lambda t: t["entry_time"])
    bh = buy_and_hold_pct(df, train_bars, len(df)) if len(df) > train_bars else 0.0
    return dict(strategy=strat_name, windows=windows, oos=metrics(oos_trades),
                p_value=bootstrap_pvalue([t["ret"] for t in oos_trades]),
                buy_hold_pct=bh, n_windows=len(windows),
                windows_active=sum(1 for w in windows if w["chosen"]),
                windows_profitable=sum(1 for w in windows if w["chosen"] and w["oos"]["ret_pct"] > 0))
