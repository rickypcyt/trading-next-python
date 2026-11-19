"""Ejecuta el walk-forward para varios simbolos/estrategias y escribe un reporte.

Uso (desde backend/):  python -m research.run --days 1095
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .data import load_klines
from .engine import Costs
from .strategies import STRATEGIES
from .walkforward import walk_forward

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--strategies", nargs="+", default=list(STRATEGIES))
    ap.add_argument("--days", type=int, default=1095)
    ap.add_argument("--train-days", type=int, default=180)
    ap.add_argument("--test-days", type=int, default=60)
    ap.add_argument("--shorts", action="store_true", help="permitir cortos (ignora funding)")
    ap.add_argument("--fee", type=float, default=0.001)
    ap.add_argument("--slippage", type=float, default=0.0005)
    a = ap.parse_args()

    costs = Costs(fee=a.fee, slippage=a.slippage)
    results = []
    print(f"{'symbol':8} {'strategy':16} {'trades':>6} {'win%':>6} {'PF':>5} {'ret%':>8} {'B&H%':>8} "
          f"{'maxDD%':>7} {'t':>5} {'p':>6} {'win+/act':>8}")
    for sym in a.symbols:
        df = load_klines(sym, "1h", a.days)
        for name in a.strategies:
            r = walk_forward(df, name, costs, a.train_days, a.test_days, shorts=a.shorts)
            r["symbol"], r["bars"] = sym, len(df)
            results.append(r)
            m = r["oos"]
            print(f"{sym:8} {name:16} {m['n']:6d} {m['win_rate']:6.1f} {min(m['profit_factor'], 99):5.2f} "
                  f"{m['ret_pct']:8.2f} {r['buy_hold_pct']:8.2f} {m['max_dd_pct']:7.2f} {m['tstat']:5.2f} "
                  f"{r['p_value']:6.3f} {r['windows_profitable']:>3}/{r['windows_active']:<4}")

    k = len(results)
    bonf = 0.05 / max(k, 1)
    winners = [r for r in results if r["oos"]["ret_pct"] > 0 and r["p_value"] < bonf and r["oos"]["n"] >= 30]
    pos = [r for r in results if r["oos"]["ret_pct"] > 0]
    print(f"\nCombinaciones probadas: {k}. Con retorno OOS > 0: {len(pos)}. "
          f"Significativas tras Bonferroni (p < {bonf:.4f}, >=30 trades): {len(winners)}")
    for r in winners:
        print(f"  -> {r['symbol']} {r['strategy']}: {r['oos']['ret_pct']:.1f}% OOS (B&H {r['buy_hold_pct']:.1f}%)")

    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    path = out / f"walkforward_{datetime.now(timezone.utc):%Y%m%d_%H%M}.json"
    path.write_text(json.dumps(dict(config=vars(a), results=results, winners=len(winners)), default=str, indent=1))
    print(f"\nReporte: {path}")


if __name__ == "__main__":
    main()
