"""Global risk and capital settings for trading engines."""
import os

ACCOUNT_CAPITAL: float = float(os.getenv("ACCOUNT_CAPITAL", "100.0"))
"""Capital disponible por cuenta en USD. Ajustar según balance real."""

RISK_LEVEL: str = os.getenv("RISK_LEVEL", "MODERATE").upper()
"""Nivel de riesgo: CONSERVATIVE, MODERATE o AGGRESSIVE."""

LEVERAGE: float = float(os.getenv("LEVERAGE", "1.0"))
"""Apalancamiento para los motores que lo soporten."""
