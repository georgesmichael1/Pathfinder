import numpy as np
from typing import Tuple, List

# Here is where DOA.py links to your separate files in the same folder:
from initialization import initialization
from attack import attack
from get_binary import get_binary
from survival_rate import survival_rate


def decode_position_to_route(position_vector: np.ndarray, round_trip: bool = True) -> List[int]:
    perm = list(np.argsort(position_vector) + 1)
    route = [0] + perm
    if round_trip:
        route.append(0)
    return route


def route_cost(route: List[int], cost_matrix: np.ndarray) -> float:
    return sum(float(cost_matrix[route[i], route[i + 1]]) for i in range(len(route) - 1))


def doa_optimize_route(
    cost_matrix: np.ndarray,
    search_agents_no: int = 60,
    max_iter: int = 150,
    round_trip: bool = True
) -> Tuple[float, List[int], List[float]]:
    """Direct translation of DOA.m adapted for route optimization"""
    num_stops = cost_matrix.shape[0]
    dim = num_stops - 1
    lb, ub = -10.0, 10.0
    P, Q = 0.5, 0.7
    na_ini = 2
    na_end = max(2, int(search_agents_no // na_ini))

    def fobj(pos_vec: np.ndarray) -> float:
        return route_cost(decode_position_to_route(pos_vec, round_trip), cost_matrix)

    positions = initialization(search_agents_no, dim, ub, lb)
    fitness = np.array([fobj(positions[i, :]) for i in range(search_agents_no)], dtype=float)

    min_idx = int(np.argmin(fitness))
    v_min = float(fitness[min_idx])
    the_best_vct = positions[min_idx, :].copy()
    v_max = float(np.max(fitness))

    convergence_curve = [v_min]
    survival = survival_rate(fitness, v_min, v_max)
    v = np.zeros_like(positions)

    for t in range(max_iter):
        for r in range(search_agents_no):
            beta1 = -2.0 + 4.0 * np.random.rand()
            beta2 = -1.0 + 2.0 * np.random.rand()
            na = int(np.round(na_ini + (na_end - na_ini) * np.random.rand()))

            if np.random.rand() < P:
                sumatory = attack(search_agents_no, na, positions, r)
                if np.random.rand() < Q:
                    v[r, :] = beta1 * sumatory - the_best_vct
                else:
                    r1 = int(np.floor(np.random.rand() * search_agents_no))
                    v[r, :] = the_best_vct + beta1 * np.exp(beta2) * (positions[r1, :] - positions[r, :])
            else:
                r1 = int(np.floor(np.random.rand() * search_agents_no))
                v[r, :] = (np.exp(beta2) * positions[r1, :] - ((-1) ** get_binary()) * positions[r, :]) / 2.0

            if survival[r] <= 0.3:
                r1 = int(np.floor(np.random.rand() * search_agents_no))
                r2 = int(np.floor(np.random.rand() * search_agents_no))
                while r1 == r2 and search_agents_no > 1:
                    r2 = int(np.floor(np.random.rand() * search_agents_no))
                v[r, :] = the_best_vct + (positions[r1, :] - ((-1) ** get_binary()) * positions[r2, :]) / 2.0

            v[r, :] = np.clip(v[r, :], lb, ub)
            f_new = fobj(v[r, :])

            if f_new <= fitness[r]:
                positions[r, :] = v[r, :].copy()
                fitness[r] = f_new
            if f_new <= v_min:
                the_best_vct = v[r, :].copy()
                v_min = f_new

        convergence_curve.append(v_min)
        v_max = float(np.max(fitness))
        survival = survival_rate(fitness, v_min, v_max)

    best_route = decode_position_to_route(the_best_vct, round_trip)
    return v_min, best_route, convergence_curve