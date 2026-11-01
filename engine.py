# engine.py
import math
import urllib.parse
import requests
import numpy as np
from typing import Dict, Any, List
from schema import RouteOptimizationInput
from doa import doa_optimize_route, route_cost

HEADERS = {"User-Agent": "Streamline-DOA-Router/1.0"}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_osrm_road_matrices(stops) -> Dict[str, Any]:
    """
    Calls the free OSRM public routing table API to get real road distances (km)
    and driving times (minutes) between all stops. Falls back to Haversine x 1.30
    road winding factor if offline.
    """
    n = len(stops)
    coords_str = ";".join([f"{s.lon},{s.lat}" for s in stops])
    url = f"https://router.project-osrm.org/table/v1/driving/{coords_str}?annotations=distance,duration"
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        res.raise_for_status()
        data = res.json()
        dist_km = np.array(data["distances"], dtype=float) / 1000.0
        dur_min = np.array(data["durations"], dtype=float) / 60.0
        return {"dist_km": dist_km, "dur_min": dur_min, "source": "OSRM Live Road Network"}
    except Exception:
        dist_km = np.zeros((n, n), dtype=float)
        dur_min = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(n):
                if i != j:
                    d = _haversine_km(stops[i].lat, stops[i].lon, stops[j].lat, stops[j].lon) * 1.30
                    dist_km[i, j] = d
                    dur_min[i, j] = (d / 35.0) * 60.0
        return {"dist_km": dist_km, "dur_min": dur_min, "source": "Geometric Road Estimate (Fallback)"}


def fetch_osrm_route_geometry(ordered_stops) -> List[List[float]]:
    """ Fetches the exact street-level polyline to draw on the map. """
    coords_str = ";".join([f"{s.lon},{s.lat}" for s in ordered_stops])
    url = f"https://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
    try:
        res = requests.get(url, headers=HEADERS, timeout=12).json()
        coords = res["routes"][0]["geometry"]["coordinates"]
        return [[c[1], c[0]] for c in coords]
    except Exception:
        return [[s.lat, s.lon] for s in ordered_stops]


def run_doa_route_engine(payload: RouteOptimizationInput) -> Dict[str, Any]:
    stops = payload.stops
    n = len(stops)
    matrices = fetch_osrm_road_matrices(stops)
    dist_mat = matrices["dist_km"]
    dur_mat = matrices["dur_min"]

    # Choose optimization target matrix
    target_mat = dur_mat if "Time" in payload.optimize_target else dist_mat

    # 1. Baseline unoptimized route (0 -> 1 -> 2 -> ... -> N-1 [-> 0])
    naive_route = list(range(n)) + ([0] if payload.round_trip else [])
    naive_dist_km = route_cost(naive_route, dist_mat)
    naive_dur_min = route_cost(naive_route, dur_mat)
    naive_fuel_cost = (naive_dist_km / 100.0) * payload.fuel_consumption_l_per_100km * payload.fuel_price_per_liter

    # 2. Run Dingo Optimization Algorithm (DOA)
    _, best_route, conv_curve = doa_optimize_route(
        cost_matrix=target_mat,
        search_agents_no=payload.search_agents_no,
        max_iter=payload.max_iterations,
        round_trip=payload.round_trip
    )

    opt_dist_km = route_cost(best_route, dist_mat)
    opt_dur_min = route_cost(best_route, dur_mat)
    opt_fuel_liters = (opt_dist_km / 100.0) * payload.fuel_consumption_l_per_100km
    opt_fuel_cost = opt_fuel_liters * payload.fuel_price_per_liter

    dist_saved_km = max(0.0, naive_dist_km - opt_dist_km)
    time_saved_min = max(0.0, naive_dur_min - opt_dur_min)
    fuel_saved_cost = max(0.0, naive_fuel_cost - opt_fuel_cost)
    pct_improvement = (dist_saved_km / naive_dist_km * 100.0) if naive_dist_km > 0 else 0.0

    # 3. Build Turn-by-Turn Manifest Table & Google Maps Navigation Link
    manifest = []
    cum_dist = 0.0
    cum_time = 0.0
    ordered_stop_objs = [stops[idx] for idx in best_route]

    for step_idx, stop_idx in enumerate(best_route):
        s = stops[stop_idx]
        leg_dist = 0.0 if step_idx == 0 else float(dist_mat[best_route[step_idx - 1], stop_idx])
        leg_time = 0.0 if step_idx == 0 else float(dur_mat[best_route[step_idx - 1], stop_idx])
        cum_dist += leg_dist
        cum_time += leg_time
        manifest.append({
            "step": step_idx + 1,
            "stop_id": stop_idx,
            "name": s.name,
            "lat": s.lat,
            "lon": s.lon,
            "leg_dist_km": round(leg_dist, 2),
            "leg_time_min": round(leg_time, 1),
            "cum_dist_km": round(cum_dist, 2),
            "cum_time_min": round(cum_time, 1)
        })

    # Google Maps Multi-Stop URL (supports up to 10 waypoints per batch link)
    gmaps_points = "/".join([f"{s.lat},{s.lon}" for s in ordered_stop_objs[:11]])
    google_maps_url = f"https://www.google.com/maps/dir/{gmaps_points}"

    road_polyline = fetch_osrm_route_geometry(ordered_stop_objs)

    return {
        "routing_source": matrices["source"],
        "naive_route": naive_route,
        "best_route": best_route,
        "naive_dist_km": round(naive_dist_km, 2),
        "opt_dist_km": round(opt_dist_km, 2),
        "dist_saved_km": round(dist_saved_km, 2),
        "pct_improvement": round(pct_improvement, 1),
        "naive_dur_min": round(naive_dur_min, 1),
        "opt_dur_min": round(opt_dur_min, 1),
        "time_saved_min": round(time_saved_min, 1),
        "opt_fuel_liters": round(opt_fuel_liters, 2),
        "opt_fuel_cost": round(opt_fuel_cost, 2),
        "fuel_saved_cost": round(fuel_saved_cost, 2),
        "currency": payload.currency_label,
        "convergence_curve": [round(val, 2) for val in conv_curve],
        "manifest": manifest,
        "road_polyline": road_polyline,
        "google_maps_url": google_maps_url
    }