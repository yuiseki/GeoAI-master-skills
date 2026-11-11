"""Create figures of recorded observations; do not infer coverage between them."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path("projects/_telecom/south-sudan-unmiss-telecom-gap")
OUT = ROOT / "outputs"
SITE_PATH = OUT / "unmiss_record_proximity.csv"
if not SITE_PATH.exists():
    SITE_PATH = OUT / "legacy_unmiss_site_cellular_distance.csv"
SITES = pd.read_csv(SITE_PATH, encoding="utf-8")
OOKLA = pd.read_csv(OUT / "ookla_mobile_tiles_ssd.csv", encoding="utf-8")
OPENCELLID = pd.read_csv(OUT / "opencellid_record_proximity.csv", encoding="utf-8")

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def plot_record_proximity():
    """Compare proximity to mapped records, explicitly not service coverage."""
    series = [
        ("OpenCelliD registered cell record", "nearest_any_record_distance_km", "#756bb1", OPENCELLID),
        ("Ookla 2024 Q2 mobile tile", "dist_ookla_tile_km" if "dist_ookla_tile_km" in SITES else "dist_ookla_km", "#2b8cbe"),
        ("OSM power-related point", "dist_osm_power_related_point_km" if "dist_osm_power_related_point_km" in SITES else "dist_power_gen_km", "#41ab5d"),
        ("OSM mapped power line", "dist_power_line_km", "#d95f0e"),
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    for y, series_item in enumerate(series):
        label, column, color = series_item[:3]
        source = series_item[3] if len(series_item) == 4 else SITES
        values = source[column].dropna().to_numpy()
        ax.scatter(values, [y] * len(values), alpha=0.78, s=30, color=color,
                   label=f"{label} (n={len(values)})")
        ax.plot([values.min(), values.max()], [y, y], color=color, alpha=0.22, linewidth=2)
    ax.axvline(10, color="#555555", linestyle="--", linewidth=1, label="10 km reference (not coverage)")
    ax.set_xscale("log")
    ax.set_yticks(range(len(series)), [s[0] for s in series])
    ax.set_xlabel("Distance to nearest recorded feature (km; logarithmic scale)")
    ax.set_title("UNMISS deployment-coordinate clusters and nearest mapped records")
    ax.text(0.01, -0.20,
            "Proximity does not establish radio service, feature operation, or UNMISS access. "
            "UN deployment points are automatically extracted map positions.",
            transform=ax.transAxes, fontsize=9, va="top", wrap=True)
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    fig.subplots_adjust(left=0.24, right=0.73, top=0.91, bottom=0.18)
    fig.savefig(OUT / "recorded_feature_proximity.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_observed_ookla_tiles():
    """Plot tile-centre observations only; no spatial interpolation."""
    fig, ax = plt.subplots(figsize=(9, 7))
    points = ax.scatter(
        OOKLA["lon"], OOKLA["lat"], c=OOKLA["avg_d_kbps"] / 1000,
        s=18 + OOKLA["tests"].clip(upper=30), cmap="viridis", alpha=0.82,
        edgecolors="white", linewidths=0.25,
    )
    colorbar = fig.colorbar(points, ax=ax)
    colorbar.set_label("Mean download speed reported for tile (Mbps)")
    ax.set_xlabel("Longitude (WGS84)")
    ax.set_ylabel("Latitude (WGS84)")
    ax.set_title("Ookla mobile test tiles with observations, 2024 Q2 (n=152)")
    ax.set_aspect(1 / 0.99)  # South Sudan lies near 7°N; compensate longitude scale approximately.
    ax.text(0.01, -0.16,
            "Only tile-centre observations are shown. Blank areas mean no plotted tile, "
            "not zero speed or absence of service; point size reflects test count (capped at 30).",
            transform=ax.transAxes, fontsize=9, va="top", wrap=True)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "ookla_observed_tiles.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    plot_record_proximity()
    plot_observed_ookla_tiles()
