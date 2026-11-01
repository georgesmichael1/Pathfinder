import numpy as np
from typing import List
from findrep import findrep  # <-- Here is how it calls findrep.py

def vector_attack(search_agents_no: int, na: int) -> np.ndarray:
    """Direct translation of vectorAttack.m"""
    v_attack: List[int] = []
    while len(v_attack) < na:
        idx = int(np.floor(np.random.rand() * search_agents_no))
        if not findrep(idx, v_attack):
            v_attack.append(idx)
    return np.array(v_attack, dtype=int)