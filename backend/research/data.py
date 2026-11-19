"""Descarga y cache de velas (klines) públicas de Binance. No requiere API key."""
import time
from pathlib import Path

import pandas as pd
import requests

URL = "https://api.binance.com/api/v3/klines"
DATA_DIR = Path(__file__).parent / "data"
INTERVAL_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
COLS = ["open", "high", "low", "close", "volume"]


def _download(symbol: str, interval: str, start_ms: int, end_ms: int) -> list:
    rows, cur = [], start_ms
    while cur < end_ms:
        r = requests.get(
            URL,
            params=dict(symbol=symbol, interval=interval, startTime=cur, endTime=end_ms, limit=1000),
            timeout=20,
        )
        r.raise_for_status()
        chunk = r.json()
        if not chunk:
            break
        rows += chunk
        cur = chunk[-1][0] + INTERVAL_MS[interval]
        if len(chunk) < 1000:
            break
        time.sleep(0.12)
    return rows


def _to_frame(rows: list, now_ms: int) -> pd.DataFrame:
    # Solo velas CERRADAS (close_time < ahora): la vela en formación se filtra.
    rows = [r for r in rows if r[6] < now_ms]
    if not rows:
        return pd.DataFrame(columns=COLS)
    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ["t"] + COLS
    df.index = pd.to_datetime(df.pop("t"), unit="ms", utc=True)
    return df.astype(float)


def load_klines(symbol: str, interval: str = "1h", days: int = 1095) -> pd.DataFrame:
    """Velas cerradas de los últimos `days` días, con cache CSV incremental."""
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{symbol}_{interval}.csv"
    step = INTERVAL_MS[interval]
    now_ms = int(time.time() * 1000)

    old = None
    if path.exists():
        old = pd.read_csv(path, index_col=0)
        old.index = pd.to_datetime(old.index, utc=True)
        start_ms = int(old.index[-1].timestamp() * 1000) + step
    else:
        start_ms = now_ms - days * 86_400_000

    new = _to_frame(_download(symbol, interval, start_ms, now_ms), now_ms)
    df = pd.concat([old, new]) if old is not None else new
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.to_csv(path)
    cutoff = df.index[-1] - pd.Timedelta(days=days)
    return df[df.index >= cutoff]
