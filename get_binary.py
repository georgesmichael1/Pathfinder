import numpy as np

def get_binary() -> int:
    """Direct translation of getBinary.m (Eq. 4 and 6)"""
    return 0 if np.random.rand() < 0.5 else 1