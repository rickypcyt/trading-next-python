"""Probabilidades 'justas' para los simuladores sinteticos.

Antes los simuladores fijaban win rates inventados (70%, 85%, 93%, 94%...), lo que fabricaba un edge que no existe.
En un paseo aleatorio sin drift, la probabilidad de tocar el take profit antes que el stop loss es
dist_SL / (dist_SL + dist_TP). Con esa probabilidad el valor esperado antes de costos es 0.

OJO: aun asi estos simuladores son SINTETICOS (demo de UI). La evidencia real esta en `research/`.
"""


def fair_win_probability(entry: float, take_profit: float, stop_loss: float, default: float = 0.5) -> float:
    try:
        d_tp, d_sl = abs(take_profit - entry), abs(entry - stop_loss)
    except TypeError:
        return default
    total = d_tp + d_sl
    return d_sl / total if total > 0 else default


def fair_win_probability_rr(reward_risk_ratio: float) -> float:
    """P(ganar) justa para un trade con ratio recompensa:riesgo dado (1:3 -> 25%)."""
    return 1.0 / (1.0 + reward_risk_ratio) if reward_risk_ratio and reward_risk_ratio > 0 else 0.5
