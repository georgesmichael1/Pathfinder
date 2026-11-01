import numpy as np

def survival_rate(fit: np.ndarray, v_min: float, v_max: float) -> np.ndarray:
    """Direct translation of survival_rate.m"""
    denom = v_max - v_min
    if abs(denom) < 1e-12:
        return np.ones_like(fit, dtype=float)
    return (v_max - fit) / denom