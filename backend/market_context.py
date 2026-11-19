import asyncio
import math
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

# Load keys if available; Client() works without keys for public market data
load_dotenv()

INTERVAL_PER_YEAR = {
    "1d": 365,
    "1h": 365 * 24,
    "1m": 365 * 24 * 60,
}

TIMEFRAME_SPECS: Dict[str, Dict[str, Any]] = {
    "5y": {"interval": "1d", "days": 1825, "threshold": 20.0},
    "1y": {"interval": "1d", "days": 365, "threshold": 10.0},
    "6m": {"interval": "1d", "days": 180, "threshold": 8.0},
    "3m": {"interval": "1d", "days": 90, "threshold": 5.0},
    "1m": {"interval": "1d", "days": 30, "threshold": 3.0},
    "1w": {"interval": "1h", "days": 7, "threshold": 3.0},
    "24h": {"interval": "1h", "days": 1, "threshold": 1.0},
    "1h": {"interval": "1m", "days": 0, "hours": 2, "threshold": 0.3},
}


@dataclass
class TimeframeMetrics:
    label: str
    interval: str
    start: datetime
    end: datetime
    candles: int
    current_price: float
    return_pct: float
    trend_direction: str
    trend_strength: float
    volatility: float
    drawdown: float
    current_drawdown: float
    max_price: float
    min_price: float
    support: float
    resistance: float
    atr: float
    atr_pct: float
    sharpe: float
    beta: float
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    volume: float
    volume_change: float
    ema_20: float
    ema_50: float
    ema_200: float
    data: pd.DataFrame = field(repr=False)


def _create_binance_client() -> Client:
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    try:
        if api_key and api_secret:
            return Client(api_key, api_secret)
        return Client()
    except Exception as exc:
        print(f"[market_context] Binance client error: {exc}")
        return Client()


class MarketContextEngine:
    """Fetch market data and compute multi-timeframe metrics from Binance."""

    def __init__(self, default_symbol: str = "BTCUSDT", cache_ttl: int = 120):
        self.default_symbol = default_symbol
        self.client = _create_binance_client()
        self.cache: Dict[str, Tuple[float, Dict]] = {}
        self.cache_ttl = cache_ttl

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------
    async def _fetch_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> Optional[List[List]]:
        try:
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)
            klines = await asyncio.to_thread(
                self.client.get_historical_klines,
                symbol=symbol,
                interval=interval,
                start_str=start_ms,
                end_str=end_ms,
                limit=limit,
            )
            return klines
        except Exception as exc:
            print(f"[market_context] Error fetching {symbol} {interval}: {exc}")
            return None

    def _klines_to_dataframe(self, klines: List[List]) -> Optional[pd.DataFrame]:
        if not klines:
            return None
        data = []
        for k in klines:
            data.append(
                {
                    "timestamp": datetime.fromtimestamp(int(k[0]) / 1000),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
            )
        df = pd.DataFrame(data)
        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # RSI 14
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14, min_periods=1).mean()
        avg_loss = loss.rolling(window=14, min_periods=1).mean()
        rs = avg_gain / (avg_loss + 1e-12)
        df["rsi"] = 100 - (100 / (1 + rs))

        # EMAs
        df["ema_20"] = close.ewm(span=20, adjust=False).mean()
        df["ema_50"] = close.ewm(span=50, adjust=False).mean()
        df["ema_200"] = close.ewm(span=200, adjust=False).mean()

        # MACD
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]

        # ATR 14
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        df["true_range"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = df["true_range"].rolling(window=14, min_periods=1).mean()

        # Returns
        df["returns"] = close.pct_change()

        return df

    def _compute_metrics(
        self,
        df: pd.DataFrame,
        interval: str,
        label: str,
        symbol: str,
        btc_df: Optional[pd.DataFrame] = None,
    ) -> Optional[TimeframeMetrics]:
        if df is None or len(df) < 10:
            return None

        df = self._calculate_indicators(df)
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        current_price = close.iloc[-1]
        start_price = close.iloc[0]
        return_pct = (current_price / start_price - 1) * 100

        threshold = TIMEFRAME_SPECS[label]["threshold"]
        if return_pct > threshold:
            trend_direction = "ALCISTA"
        elif return_pct < -threshold:
            trend_direction = "BAJISTA"
        else:
            trend_direction = "LATERAL"

        # Trend strength = R^2 of linear regression
        x = np.arange(len(close))
        try:
            slope, intercept = np.polyfit(x, close.values, 1)
            y_pred = slope * x + intercept
            ss_res = np.sum((close.values - y_pred) ** 2)
            ss_tot = np.sum((close.values - close.mean()) ** 2)
            r_squared = 1 - (ss_res / (ss_tot + 1e-12))
            trend_strength = float(r_squared)
        except Exception:
            trend_strength = 0.0

        returns = df["returns"].dropna()
        periods_per_year = INTERVAL_PER_YEAR.get(interval, 365)
        if len(returns) > 1:
            mean_ret = returns.mean()
            std_ret = returns.std()
            volatility = std_ret * math.sqrt(periods_per_year) * 100
            sharpe = (
                (mean_ret / (std_ret + 1e-12)) * math.sqrt(periods_per_year)
                if std_ret > 1e-12
                else 0.0
            )
        else:
            volatility = 0.0
            sharpe = 0.0

        peak = close.cummax()
        dd_series = (close - peak) / peak
        drawdown = float(-dd_series.min() * 100)
        current_drawdown = float(-dd_series.iloc[-1] * 100)

        max_price = float(high.max())
        min_price = float(low.min())

        lookback = min(max(14, len(df) // 4), len(df))
        support = float(low.tail(lookback).min())
        resistance = float(high.tail(lookback).max())

        atr = float(df["atr"].iloc[-1]) if "atr" in df else 0.0
        atr_pct = (atr / current_price * 100) if current_price > 0 else 0.0

        # Beta vs BTC
        beta = 1.0
        if btc_df is not None and symbol != "BTCUSDT" and len(btc_df) > 10:
            try:
                sym_rets = df.set_index("timestamp")["close"].pct_change().dropna()
                btc_rets = btc_df.set_index("timestamp")["close"].pct_change().dropna()
                common = pd.concat([sym_rets, btc_rets], axis=1).dropna()
                if len(common) > 2:
                    cov = np.cov(common.iloc[:, 0], common.iloc[:, 1])[0, 1]
                    var = np.var(common.iloc[:, 1])
                    beta = cov / (var + 1e-12)
            except Exception:
                beta = 1.0

        avg_volume = volume.tail(min(20, len(df))).mean()
        last_volume = volume.iloc[-1]
        volume_change = (
            ((last_volume / avg_volume) - 1) * 100 if avg_volume > 0 else 0.0
        )

        rsi = float(df["rsi"].iloc[-1]) if "rsi" in df else 50.0
        macd = float(df["macd"].iloc[-1]) if "macd" in df else 0.0
        macd_signal = float(df["macd_signal"].iloc[-1]) if "macd_signal" in df else 0.0
        macd_histogram = float(df["macd_histogram"].iloc[-1]) if "macd_histogram" in df else 0.0

        ema_20 = float(df["ema_20"].iloc[-1]) if "ema_20" in df else current_price
        ema_50 = float(df["ema_50"].iloc[-1]) if "ema_50" in df else current_price
        ema_200 = float(df["ema_200"].iloc[-1]) if "ema_200" in df else current_price

        return TimeframeMetrics(
            label=label,
            interval=interval,
            start=df["timestamp"].iloc[0],
            end=df["timestamp"].iloc[-1],
            candles=len(df),
            current_price=float(current_price),
            return_pct=float(return_pct),
            trend_direction=trend_direction,
            trend_strength=float(trend_strength),
            volatility=float(volatility),
            drawdown=float(drawdown),
            current_drawdown=float(current_drawdown),
            max_price=max_price,
            min_price=min_price,
            support=float(support),
            resistance=float(resistance),
            atr=float(atr),
            atr_pct=float(atr_pct),
            sharpe=float(sharpe),
            beta=float(beta),
            rsi=float(rsi),
            macd=float(macd),
            macd_signal=float(macd_signal),
            macd_histogram=float(macd_histogram),
            volume=float(avg_volume),
            volume_change=float(volume_change),
            ema_20=float(ema_20),
            ema_50=float(ema_50),
            ema_200=float(ema_200),
            data=df,
        )

    async def _fetch_timeframe(
        self, symbol: str, label: str, spec: Dict, end_time: datetime
    ) -> Optional[TimeframeMetrics]:
        interval = spec["interval"]
        days = spec.get("days", 0)
        hours = spec.get("hours", 0)
        if days == 0 and hours == 0:
            hours = 2
        start_time = end_time - timedelta(days=days, hours=hours)

        klines = await self._fetch_historical_klines(
            symbol, interval, start_time, end_time, limit=1000
        )
        df = self._klines_to_dataframe(klines)
        if df is None or len(df) < 10:
            return None
        return df

    async def _get_timeframe(
        self,
        symbol: str,
        label: str,
        end_time: datetime,
        btc_df: Optional[pd.DataFrame] = None,
    ) -> Optional[TimeframeMetrics]:
        spec = TIMEFRAME_SPECS[label]
        df = await self._fetch_timeframe(symbol, label, spec, end_time)
        if df is None:
            return None
        return self._compute_metrics(df, spec["interval"], label, symbol, btc_df)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_market_context(
        self, symbol: str, refresh: bool = False
    ) -> Dict[str, Any]:
        """Return context across all configured timeframes."""
        symbol = symbol.upper()
        now = time.time()
        if not refresh and symbol in self.cache:
            cached_at, cached = self.cache[symbol]
            if now - cached_at < self.cache_ttl:
                return cached

        end_time = datetime.utcnow()
        # Fetch BTC data once for beta calculations
        btc_klines = await self._fetch_historical_klines(
            "BTCUSDT", "1d", end_time - timedelta(days=400), end_time, limit=1000
        )
        btc_df = self._klines_to_dataframe(btc_klines)

        timeframes: Dict[str, Optional[TimeframeMetrics]] = {}
        for label in TIMEFRAME_SPECS.keys():
            tf = await self._get_timeframe(symbol, label, end_time, btc_df)
            if tf is not None:
                timeframes[label] = tf

        if not timeframes:
            return {
                "symbol": symbol,
                "error": "No se pudieron obtener datos de mercado.",
                "timeframes": {},
                "summary": {},
            }

        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "current_price": (timeframes.get("1h") or timeframes.get("24h") or list(timeframes.values())[0]).current_price,
            "timeframes": {
                label: self._timeframe_to_dict(tf) for label, tf in timeframes.items()
            },
            "summary": self._build_summary(timeframes),
        }
        self.cache[symbol] = (now, result)
        return result

    def _timeframe_to_dict(self, tf: TimeframeMetrics) -> Dict[str, Any]:
        return {
            "label": tf.label,
            "interval": tf.interval,
            "start": tf.start.isoformat(),
            "end": tf.end.isoformat(),
            "candles": tf.candles,
            "current_price": tf.current_price,
            "return_pct": round(tf.return_pct, 2),
            "trend_direction": tf.trend_direction,
            "trend_strength": round(tf.trend_strength, 3),
            "volatility": round(tf.volatility, 2),
            "drawdown": round(tf.drawdown, 2),
            "current_drawdown": round(tf.current_drawdown, 2),
            "max_price": round(tf.max_price, 2),
            "min_price": round(tf.min_price, 2),
            "support": round(tf.support, 2),
            "resistance": round(tf.resistance, 2),
            "atr": round(tf.atr, 4),
            "atr_pct": round(tf.atr_pct, 2),
            "sharpe": round(tf.sharpe, 2),
            "beta": round(tf.beta, 2),
            "rsi": round(tf.rsi, 2),
            "macd": round(tf.macd, 4),
            "macd_signal": round(tf.macd_signal, 4),
            "macd_histogram": round(tf.macd_histogram, 4),
            "volume": round(tf.volume, 2),
            "volume_change": round(tf.volume_change, 2),
            "ema_20": round(tf.ema_20, 2),
            "ema_50": round(tf.ema_50, 2),
            "ema_200": round(tf.ema_200, 2),
        }

    def _build_summary(
        self, timeframes: Dict[str, TimeframeMetrics]
    ) -> Dict[str, Any]:
        def get(label: str):
            return timeframes.get(label)

        tf_long = get("1y") or get("5y") or get("6m")
        tf_medium = get("6m") or get("3m") or get("1m")
        tf_short = get("24h") or get("1h") or get("1w")
        tf_current = get("1h") or get("24h")

        summary = {
            "current_price": tf_current.current_price if tf_current else None,
            "tendencia_largo_plazo": tf_long.trend_direction if tf_long else None,
            "tendencia_media": tf_medium.trend_direction if tf_medium else None,
            "tendencia_corta": tf_short.trend_direction if tf_short else None,
            "correccion_actual": None,
            "rsi": None,
            "macd": None,
            "volumen": None,
            "volatilidad": None,
            "drawdown": None,
            "soporte": None,
            "resistencia": None,
            "atr": None,
            "atr_pct": None,
            "beta": None,
            "sharpe": None,
        }

        if tf_current:
            summary["rsi"] = round(tf_current.rsi, 2)
            summary["macd"] = round(tf_current.macd, 4)
            summary["volumen"] = round(tf_current.volume_change, 2)
            summary["volatilidad"] = round(tf_current.volatility, 2)

        if tf_short:
            summary["correccion_actual"] = round(
                (tf_short.current_price / tf_short.max_price - 1) * 100, 2
            )
            summary["drawdown"] = round(tf_short.drawdown, 2)
            summary["soporte"] = round(tf_short.support, 2)
            summary["resistencia"] = round(tf_short.resistance, 2)
            summary["atr"] = round(tf_short.atr, 4)
            summary["atr_pct"] = round(tf_short.atr_pct, 2)

        if tf_medium:
            summary["beta"] = round(tf_medium.beta, 2)
            summary["sharpe"] = round(tf_medium.sharpe, 2)

        if tf_long:
            summary["max_price"] = round(tf_long.max_price, 2)
            summary["min_price"] = round(tf_long.min_price, 2)

        return summary

    async def get_current_price(self, symbol: str) -> float:
        try:
            ticker = await asyncio.to_thread(self.client.get_symbol_ticker, symbol=symbol.upper())
            return float(ticker["price"])
        except Exception as exc:
            print(f"[market_context] Error fetching price: {exc}")
            return 0.0


# Global instance
market_context_engine = MarketContextEngine()


if __name__ == "__main__":
    ctx = asyncio.run(market_context_engine.get_market_context("BTCUSDT"))
    print(ctx)
