from typing import Dict, List


REGIME_STRATEGIES = {
    "BULL_MARKET": ["TREND_FOLLOWING"],
    "BEAR_MARKET": ["RSI", "BOLLINGER"],
    "SIDEWAYS": ["MEAN_REVERSION"],
    "HIGH_VOLATILITY": ["SCALPING", "BOLLINGER"],
    "CRASH": ["NO_OPERAR"],
    "RALLY": ["MOMENTUM"],
}

REGIME_DESCRIPTIONS = {
    "BULL_MARKET": "Tendencia alcista sostenida en mediano-largo plazo. Ideal para seguir la tendencia.",
    "BEAR_MARKET": "Tendencia bajista sostenida. Priorizar estrategias de corto o reversión.",
    "SIDEWAYS": "Mercado lateral sin dirección clara. Aprovechar reversiones a la media.",
    "HIGH_VOLATILITY": "Movimientos bruscos y amplio rango. Reducir tamaño y ser selectivo.",
    "CRASH": "Pérdidas aceleradas y pánico. Lo más seguro es no operar.",
    "RALLY": "Subida rápida y alcista. Puede ser momentum, vigilar sobrecompra.",
}


class MarketRegimeDetector:
    """Detect the current market regime from multi-timeframe context."""

    def detect(self, context: Dict) -> Dict:
        """Return a regime classification with recommended strategies."""
        timeframes = context.get("timeframes", {})
        if not timeframes:
            return self._fallback()

        def get(label: str, key: str, default: float = 0.0):
            tf = timeframes.get(label)
            return tf.get(key, default) if tf else default

        def get_summary(key: str, default: float = 0.0):
            return context.get("summary", {}).get(key, default)

        long_return = get("5y", "return_pct", 0.0) or get("1y", "return_pct", 0.0)
        medium_return = (
            get("6m", "return_pct", 0.0)
            or get("3m", "return_pct", 0.0)
            or get("1m", "return_pct", 0.0)
        )
        short_return = (
            get("1w", "return_pct", 0.0)
            or get("24h", "return_pct", 0.0)
            or get("1h", "return_pct", 0.0)
        )
        volatility = get("1y", "volatility", 0.0) or get("6m", "volatility", 0.0)
        drawdown = get("1y", "drawdown", 0.0) or get("5y", "drawdown", 0.0)
        correction = get_summary("correccion_actual", 0.0)

        regime, confidence, risk_bias = self._classify(
            long_return, medium_return, short_return, volatility, drawdown, correction
        )

        return {
            "regime": regime,
            "confidence": round(confidence, 2),
            "risk_bias": risk_bias,
            "recommended_strategies": REGIME_STRATEGIES.get(regime, ["ESPERAR"]),
            "description": REGIME_DESCRIPTIONS.get(regime, "Régimen desconocido."),
            "inputs": {
                "long_return": round(long_return, 2),
                "medium_return": round(medium_return, 2),
                "short_return": round(short_return, 2),
                "volatility": round(volatility, 2),
                "drawdown": round(drawdown, 2),
                "correction": round(correction, 2),
            },
        }

    def _classify(
        self,
        long_return: float,
        medium_return: float,
        short_return: float,
        volatility: float,
        drawdown: float,
        correction: float,
    ) -> (str, float, str):
        # Crash: strong recent drop or deep correction
        if correction < -15 or (short_return < -8 and drawdown > 20):
            confidence = min(0.95, (abs(correction) + abs(short_return)) / 40)
            return "CRASH", confidence, "risk_off"

        # Rally: strong short-term upward thrust
        if short_return > 10 and medium_return > 5 and long_return >= -5:
            confidence = min(0.95, (short_return + medium_return) / 40)
            return "RALLY", confidence, "risk_on"

        # High volatility: wide swings without clear crash/rally
        if volatility > 80 and abs(short_return) < 10:
            confidence = min(0.85, volatility / 150)
            return "HIGH_VOLATILITY", confidence, "risk_off"

        # Bull market: long and medium term uptrend
        if long_return > 20 and medium_return > 10 and correction > -15:
            confidence = min(0.95, (long_return + medium_return) / 80)
            return "BULL_MARKET", confidence, "risk_on"

        # Bear market: long and medium term downtrend
        if long_return < -20 and medium_return < -10 and drawdown > 20:
            confidence = min(0.95, (abs(long_return) + abs(medium_return)) / 80)
            return "BEAR_MARKET", confidence, "risk_off"

        # Sideways: all returns near zero
        if abs(long_return) < 15 and abs(medium_return) < 10 and abs(short_return) < 5:
            confidence = min(0.8, 1.0 - (abs(long_return) + abs(medium_return)) / 50)
            return "SIDEWAYS", confidence, "neutral"

        # Fallback directional classification
        if long_return > 0 and medium_return > 0:
            return "BULL_MARKET", 0.55, "risk_on"
        if long_return < 0 and medium_return < 0:
            return "BEAR_MARKET", 0.55, "risk_off"
        return "SIDEWAYS", 0.55, "neutral"

    def _fallback(self) -> Dict:
        return {
            "regime": "SIDEWAYS",
            "confidence": 0.0,
            "risk_bias": "neutral",
            "recommended_strategies": ["ESPERAR"],
            "description": "Sin datos suficientes para determinar el régimen.",
            "inputs": {},
        }


# Global instance
market_regime_detector = MarketRegimeDetector()
