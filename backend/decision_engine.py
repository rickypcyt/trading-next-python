import json
import math
from typing import Dict, Optional, Tuple
from urllib.request import urlopen
from urllib.error import URLError

from market_context import market_context_engine, MarketContextEngine
from market_regime import market_regime_detector, MarketRegimeDetector


def _fetch_json(url: str, timeout: int = 5):
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, Exception):
        return None


def get_fear_greed_index() -> float:
    """Fetch the latest Fear & Greed index from alternative.me."""
    data = _fetch_json("https://api.alternative.me/fng/?limit=1")
    try:
        return float(data["data"][0]["value"])
    except (TypeError, KeyError, IndexError):
        return 50.0


def get_btc_dominance() -> float:
    """Fetch BTC dominance from CoinGecko."""
    data = _fetch_json("https://api.coingecko.com/api/v3/global")
    try:
        return float(data["data"]["market_cap_percentage"]["btc"])
    except (TypeError, KeyError, AttributeError):
        return 50.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _trend_score(return_pct: float, max_return_for_full: float) -> float:
    """Scale return so max_return_for_full maps to +/- weight limit."""
    return _clamp(return_pct / max_return_for_full * 10, -10, 10)


class DecisionEngine:
    """Multi-factor scoring engine that combines market context, regime and external data."""

    def __init__(
        self,
        context_engine: Optional[MarketContextEngine] = None,
        regime_detector: Optional[MarketRegimeDetector] = None,
    ):
        self.context_engine = context_engine or market_context_engine
        self.regime_detector = regime_detector or market_regime_detector

    async def analyze(self, symbol: str, refresh: bool = False) -> Dict:
        """Return a complete decision for the given symbol."""
        context = await self.context_engine.get_market_context(symbol, refresh=refresh)
        if "error" in context and context["error"]:
            return {
                "symbol": symbol,
                "error": context["error"],
                "score": 0,
                "probability": 0,
                "decision": "NO ENTRAR",
                "risk": "Alto",
                "direction": "NEUTRAL",
            }

        regime = self.regime_detector.detect(context)
        score, score_breakdown = self._compute_score(symbol, context, regime)
        probability = round(score)
        decision = self._decision_from_score(score)
        risk = self._risk_level(score, context, regime)
        direction = self._direction_from_decision(decision)

        return {
            "symbol": symbol,
            "current_price": context["summary"].get("current_price"),
            "timestamp": context["timestamp"],
            "context": context,
            "regime": regime,
            "score": score,
            "probability": probability,
            "decision": decision,
            "risk": risk,
            "direction": direction,
            "recommended_strategy": self._recommended_strategy(regime, decision),
            "factors": score_breakdown,
            "summary": {
                "tendencia_largo_plazo": context["summary"].get("tendencia_largo_plazo"),
                "tendencia_media": context["summary"].get("tendencia_media"),
                "tendencia_corta": context["summary"].get("tendencia_corta"),
                "correccion_actual": context["summary"].get("correccion_actual"),
                "rsi": context["summary"].get("rsi"),
                "macd": context["summary"].get("macd"),
                "volumen": context["summary"].get("volumen"),
                "volatilidad": context["summary"].get("volatilidad"),
                "soporte": context["summary"].get("soporte"),
                "resistencia": context["summary"].get("resistencia"),
                "atr_pct": context["summary"].get("atr_pct"),
                "beta": context["summary"].get("beta"),
                "sharpe": context["summary"].get("sharpe"),
            },
        }

    def _compute_score(
        self, symbol: str, context: Dict, regime: Dict
    ) -> Tuple[float, Dict]:
        timeframes = context.get("timeframes", {})
        summary = context.get("summary", {})

        def get(label: str, key: str, default=0.0):
            tf = timeframes.get(label)
            return tf.get(key, default) if tf else default

        # Prefer long-term daily for EMAs and long trend
        tf_long = timeframes.get("1y") or timeframes.get("5y") or timeframes.get("6m")
        tf_medium = timeframes.get("6m") or timeframes.get("3m") or timeframes.get("1m")
        tf_short = timeframes.get("24h") or timeframes.get("1h") or timeframes.get("1w")
        tf_current = timeframes.get("1h") or timeframes.get("24h") or tf_short

        long_return = tf_long.get("return_pct", 0.0) if tf_long else 0.0
        medium_return = tf_medium.get("return_pct", 0.0) if tf_medium else 0.0
        short_return = tf_short.get("return_pct", 0.0) if tf_short else 0.0

        current_price = tf_current.get("current_price", 0.0) if tf_current else 0.0
        rsi = tf_current.get("rsi", 50.0) if tf_current else 50.0
        macd = tf_current.get("macd", 0.0) if tf_current else 0.0
        macd_signal = tf_current.get("macd_signal", 0.0) if tf_current else 0.0
        macd_histogram = tf_current.get("macd_histogram", 0.0) if tf_current else 0.0
        volume_change = tf_current.get("volume_change", 0.0) if tf_current else 0.0
        volatility = tf_current.get("volatility", 0.0) if tf_current else 0.0
        atr_pct = tf_current.get("atr_pct", 0.0) if tf_current else 0.0
        support = tf_current.get("support", 0.0) if tf_current else 0.0
        resistance = tf_current.get("resistance", 0.0) if tf_current else 0.0

        ema_200 = tf_long.get("ema_200", current_price) if tf_long else current_price
        ema_50 = tf_long.get("ema_50", current_price) if tf_long else current_price

        fear_greed = get_fear_greed_index()
        btc_dominance = get_btc_dominance()

        factors = {}

        # Trend factors (long, medium, short)
        factors["long_trend"] = _trend_score(long_return, 30.0)
        factors["medium_trend"] = _trend_score(medium_return, 20.0)
        factors["short_trend"] = _trend_score(short_return, 5.0)

        # RSI
        if rsi < 30:
            factors["rsi"] = 10.0
        elif rsi < 40:
            factors["rsi"] = 5.0
        elif rsi > 70:
            factors["rsi"] = -10.0
        elif rsi > 60:
            factors["rsi"] = -5.0
        else:
            factors["rsi"] = 0.0

        # MACD
        if macd > macd_signal and macd_histogram > 0:
            factors["macd"] = 10.0
        elif macd < macd_signal and macd_histogram < 0:
            factors["macd"] = -10.0
        else:
            factors["macd"] = 0.0

        # EMA 200 / 50 alignment
        ema_score = 0.0
        if current_price > ema_200:
            ema_score += 7.0
        else:
            ema_score -= 7.0
        if ema_50 > ema_200:
            ema_score += 3.0
        else:
            ema_score -= 3.0
        factors["ema_alignment"] = _clamp(ema_score, -10, 10)

        # Volume
        factors["volume"] = _clamp(volume_change * 0.25, -10, 10)

        # Support / Resistance distance
        if support > 0 and resistance > 0 and current_price > 0:
            dist_support = (current_price - support) / current_price * 100
            dist_resistance = (resistance - current_price) / current_price * 100
            threshold = max(atr_pct * 2, 0.3)
            if dist_support < threshold:
                factors["support_resistance"] = 5.0
            elif dist_resistance < threshold:
                factors["support_resistance"] = -5.0
            else:
                factors["support_resistance"] = 0.0
        else:
            factors["support_resistance"] = 0.0

        # Volatility
        if volatility > 80:
            factors["volatility"] = -5.0
        elif volatility < 30:
            factors["volatility"] = 5.0
        else:
            factors["volatility"] = 0.0

        # Fear & Greed
        if fear_greed < 25:
            factors["fear_greed"] = 5.0
        elif fear_greed < 40:
            factors["fear_greed"] = 3.0
        elif fear_greed > 75:
            factors["fear_greed"] = -5.0
        elif fear_greed > 60:
            factors["fear_greed"] = -3.0
        else:
            factors["fear_greed"] = 0.0

        # BTC dominance
        is_btc = symbol.upper().startswith("BTC")
        if btc_dominance > 55:
            factors["btc_dominance"] = 5.0 if is_btc else -5.0
        elif btc_dominance > 50:
            factors["btc_dominance"] = 2.0 if is_btc else -2.0
        else:
            factors["btc_dominance"] = 0.0

        # Regime adjustment
        regime_map = {
            "BULL_MARKET": 5.0,
            "RALLY": 5.0,
            "SIDEWAYS": 0.0,
            "HIGH_VOLATILITY": -5.0,
            "BEAR_MARKET": -5.0,
            "CRASH": -10.0,
        }
        factors["regime"] = regime_map.get(regime.get("regime", "SIDEWAYS"), 0.0)

        raw_score = sum(factors.values())
        score = _clamp(raw_score, 0.0, 100.0)
        return score, {k: round(v, 2) for k, v in factors.items()}

    def _decision_from_score(self, score: float) -> str:
        if score >= 70:
            return "COMPRAR"
        if score >= 40:
            return "ESPERAR"
        if score >= 25:
            return "NO ENTRAR"
        return "VENDER"

    def _direction_from_decision(self, decision: str) -> str:
        return {"COMPRAR": "LONG", "VENDER": "SHORT"}.get(decision, "NEUTRAL")

    def _risk_level(self, score: float, context: Dict, regime: Dict) -> str:
        summary = context.get("summary", {})
        volatility = summary.get("volatilidad", 0.0) or 0.0
        drawdown = summary.get("drawdown", 0.0) or 0.0

        if regime.get("regime") == "CRASH":
            return "Alto"
        if volatility > 80 or drawdown > 20:
            return "Alto"
        if volatility > 40 or drawdown > 10 or (score < 70 and score > 40):
            return "Medio"
        return "Bajo"

    def _recommended_strategy(self, regime: Dict, decision: str) -> str:
        if decision == "NO ENTRAR" or decision == "VENDER":
            return "NO_OPERAR"
        strategies = regime.get("recommended_strategies", ["ESPERAR"])
        return strategies[0]


# Global instance
decision_engine = DecisionEngine()
