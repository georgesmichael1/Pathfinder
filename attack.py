import numpy as np
from vector_attack import vector_attack  # <-- Calls vector_attack.py

def attack(search_agents_no: int, na: int, positions: np.ndarray, r: int) -> np.ndarray:
    """Direct translation of Attack.m (Eq. 2)"""
    v_attack = vector_attack(search_agents_no, na)
    sumatory = np.zeros(positions.shape[1], dtype=float)
    for j in range(len(v_attack)):
        sumatory += positions[v_attack[j], :] - positions[r, :]
    return sumatory / float(na)