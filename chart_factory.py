# chart_factory.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import Dict, Any


def generate_doa_convergence_chart(res: Dict[str, Any], filename: str = "doa_convergence.png") -> str:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8), dpi=150)
    fig.patch.set_facecolor("#FFFFFF")

    # Left: DOA Convergence Curve
    curve = res["convergence_curve"]
    ax1.plot(range(len(curve)), curve, color="#059669", linewidth=2.2)
    ax1.fill_between(range(len(curve)), curve, min(curve), color="#10B981", alpha=0.12)
    ax1.set_title("Dingo Optimization Algorithm (DOA) Convergence", fontsize=10, fontweight="bold")
    ax1.set_xlabel("Iteration", fontsize=9)
    ax1.set_ylabel("Best Route Cost", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.4)

    # Right: Unoptimized vs DOA Optimized Comparison
    labels = ["Unoptimized Input Order", "DOA Optimized Sequence"]
    dists = [res["naive_dist_km"], res["opt_dist_km"]]
    bars = ax2.bar(labels, dists, color=["#94A3B8", "#059669"], width=0.5)
    ax2.set_title(f"Total Distance Saved: {res['dist_saved_km']} km (-{res['pct_improvement']}%)", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Total Road Distance (km)", fontsize=9)
    for b in bars:
        h = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2.0, h, f"{h:.1f} km", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close(fig)
    return filename


def generate_static_route_map(res: Dict[str, Any], filename: str = "doa_route_map.png") -> str:
    fig, ax = plt.subplots(figsize=(6.5, 4.2), dpi=150)
    manifest = res["manifest"]
    lats = [m["lat"] for m in manifest]
    lons = [m["lon"] for m in manifest]

    ax.plot(lons, lats, color="#0284C7", linewidth=2.0, linestyle="-", zorder=2, label="DOA Optimized Path")
    ax.scatter(lons, lats, color="#1E293B", s=55, zorder=3)
    ax.scatter([lons[0]], [lats[0]], color="#DC2626", s=110, zorder=4, label="Depot / Start (Stop 1)")

    for m in manifest[:-1]:
        ax.annotate(
            f"{m['step']}. {m['name'][:16]}",
            (m["lon"], m["lat"]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=7.5,
            fontweight="bold"
        )

    ax.set_title("DOA Sequenced Stop Topology", fontsize=10, fontweight="bold")
    ax.set_xlabel("Longitude", fontsize=8)
    ax.set_ylabel("Latitude", fontsize=8)
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.5)
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close(fig)
    return filename