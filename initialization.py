import numpy as np

def initialization(search_agents_no: int, dim: int, ub: float, lb: float) -> np.ndarray:
    """Direct translation of initialization.m"""
    return np.random.rand(search_agents_no, dim) * (ub - lb) + lb