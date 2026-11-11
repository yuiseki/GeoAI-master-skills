"""Explore observed mobile tile speeds, not coverage or site-level service."""
import argparse
import json
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib_fontja  # noqa: F401
import numpy as np
import pandas as pd
from pyproj import Geod

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def summarize(frame):
    good = frame.loc[frame.avg_d_kbps.notna() & (frame.avg_d_kbps > 0)]
    weights = good.tests.clip(lower=0)
    median = float(good.avg_d_kbps.median() / 1000) if len(good) else None
    return {
        "tile_count": len(frame),
        "tests": int(frame.tests.sum()),
        "valid_speed_tiles": len(good),
        "median_mbps": median,
        "q1_mbps": float(good.avg_d_kbps.quantile(.25) / 1000) if len(good) else None,
        "q3_mbps": float(good.avg_d_kbps.quantile(.75) / 1000) if len(good) else None,
        "test_weighted_mean_mbps": float(np.average(good.avg_d_kbps, weights=weights) / 1000) if weights.sum() else None,
        "ideal_1gb_minutes": 8000 / median / 60 if median else None,
    }


def run(places_path):
    places = gpd.read_parquet(places_path)
    juba = places.loc[places.NAME == "Juba"]
    if len(juba) != 1 or places.crs is None:
        raise ValueError("Natural Earth must contain exactly one Juba with a CRS")
    point = juba.to_crs(4326).geometry.iloc[0]
    frame = pd.read_csv(OUT / "ookla_mobile_tiles_ssd.csv")
    if frame[["lon", "lat", "tests"]].isna().any().any() or (frame.tests < 0).any():
        raise ValueError("missing location/test count or negative count")
    _, _, dist = Geod(ellps="WGS84").inv(np.full(len(frame), point.x), np.full(len(frame), point.y), frame.lon.to_numpy(), frame.lat.to_numpy())
    frame["juba_distance_km"] = dist / 1000
    frame["group_10km"] = np.where(frame.juba_distance_km <= 10, "juba", "other")
    frame.to_csv(OUT / "speed_comparison_tiles.csv", index=False)
    sites = pd.read_csv(OUT / "legacy_unmiss_site_cellular_distance.csv")
    site_rows = []
    for site in sites.itertuples(index=False):
        _, _, site_dist = Geod(ellps="WGS84").inv(np.full(len(frame), site.site_lon), np.full(len(frame), site.site_lat), frame.lon.to_numpy(), frame.lat.to_numpy())
        nearest = int(np.argmin(site_dist))
        tile = frame.iloc[nearest]
        site_rows.append({"unverified_map_label": site.site_name, "site_lon": site.site_lon, "site_lat": site.site_lat, "nearest_tile_distance_km": float(site_dist[nearest] / 1000), "nearest_tile_mean_download_mbps": float(tile.avg_d_kbps / 1000), "nearest_tile_tests": int(tile.tests), "tile_within_10km": bool(site_dist[nearest] <= 10000)})
    pd.DataFrame(site_rows).to_csv(OUT / "nearest_observed_speed_by_map_coordinate.csv", index=False)
    result = {"source": "Ookla mobile 2024 Q2; saved South Sudan extraction", "juba_source": "Natural Earth v5.1.2 populated places", "juba_lon": point.x, "juba_lat": point.y, "distance": "WGS84 geodesic to tile centroid", "groups": {}}
    for km in (10, 20):
        mask = frame.juba_distance_km <= km
        result["groups"][str(km)] = {"juba": summarize(frame[mask]), "other": summarize(frame[~mask])}
    (OUT / "speed_comparison.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(9, 4.8))
    for group, label, color in (("juba", "ジュバ中心から10 km以内", "#d95f02"), ("other", "10 kmより遠い地域", "#1b6c8e")):
        values = np.sort(frame.loc[(frame.group_10km == group) & (frame.avg_d_kbps > 0), "avg_d_kbps"].to_numpy() / 1000)
        if len(values):
            ax.step(values, np.arange(1, len(values) + 1) / len(values) * 100, where="post", label=f"{label}（{len(values)}タイル）", color=color)
    ax.set(xlabel="タイル平均下り速度（Mbps、対数目盛）", ylabel="この速度以下のタイルの割合（%）", title="観測タイルの下り速度：ジュバ周辺とその他")
    ax.set_xscale("log")
    ax.grid(alpha=.25)
    ax.legend(loc="lower right")
    fig.text(.08, .01, "Ookla 2024年第2四半期。未観測は含まない。1タイル1票。CC BY-NC-SA 4.0", fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(OUT / "speed_comparison.png", dpi=180)
    (OUT / "speed_comparison_figure.json").write_text(json.dumps({"question": "観測タイルの下り速度分布は地域でどう異なるか", "source": "speed_comparison_tiles.csv", "units": "one observed tile; tile-mean Mbps", "font": plt.rcParams["font.family"], "scale": "log", "count": len(frame)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--places", type=Path, required=True)
    run(parser.parse_args().places)
