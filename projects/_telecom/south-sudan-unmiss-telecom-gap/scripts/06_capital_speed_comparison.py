"""Compare observed Ookla mobile tiles around Tokyo and Juba in the same snapshot."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import duckdb
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib_fontja  # noqa: F401
import numpy as np
from pyproj import Geod

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
spec = importlib.util.spec_from_file_location("speed", Path(__file__).with_name("05_speed_comparison.py"))
speed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(speed)


def within_radius(frame, lon, lat, km):
    _, _, meters = Geod(ellps="WGS84").inv(np.full(len(frame), lon), np.full(len(frame), lat), frame.lon.to_numpy(), frame.lat.to_numpy())
    return meters <= km * 1000


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(data, places_path):
    places = gpd.read_parquet(places_path).to_crs(4326)
    centers = {}
    for name in ("Tokyo", "Juba"):
        found = places.loc[places.NAME == name]
        if len(found) != 1:
            raise ValueError(f"expected exactly one {name} in Natural Earth")
        centers[name] = (found.geometry.iloc[0].x, found.geometry.iloc[0].y)
    # Conservative bounding boxes precede the exact geodesic selection.
    conn = duckdb.connect(config={"memory_limit": "2GB", "threads": "2"})
    rows = conn.execute("""SELECT tile_x AS lon, tile_y AS lat, avg_d_kbps, tests
      FROM read_parquet(?) WHERE (tile_x BETWEEN 138.5 AND 141.0 AND tile_y BETWEEN 34.5 AND 36.8)
         OR (tile_x BETWEEN 31.0 AND 32.1 AND tile_y BETWEEN 4.3 AND 5.4)""", [str(data)]).df()
    groups = {"tokyo_10km": ("Tokyo", 10), "tokyo_50km": ("Tokyo", 50), "juba_10km": ("Juba", 10)}
    result = {"source": "Ookla mobile 2024 Q2", "input_subset_sha256": digest(data), "source_url": "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=mobile/year=2024/quarter=2/2024-04-01_performance_mobile_tiles.parquet", "accessed": "2026-11-11", "center_source": "Natural Earth v5.1.2 populated places", "centers_lon_lat": centers, "groups": {}}
    fig, ax = plt.subplots(figsize=(9, 5))
    for key, (city, km) in groups.items():
        lon, lat = centers[city]
        frame = rows.loc[within_radius(rows, lon, lat, km)]
        result["groups"][key] = speed.summarize(frame)
        values = np.sort(frame.loc[frame.avg_d_kbps > 0, "avg_d_kbps"].to_numpy() / 1000)
        if not len(values):
            raise ValueError(f"no positive speed observations for {key}")
        labels = {"tokyo_10km": "東京中心10 km以内", "tokyo_50km": "東京中心50 km以内", "juba_10km": "ジュバ中心10 km以内"}
        colors = {"tokyo_10km": "#2878a0", "tokyo_50km": "#55a868", "juba_10km": "#d95f02"}
        ax.step(values, np.arange(1, len(values) + 1) / len(values) * 100, where="post", label=f"{labels[key]}（{len(values):,}タイル）", color=colors[key])
    (OUT / "capital_speed_comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    ax.set(xlabel="タイル平均下り速度（Mbps、対数目盛）", ylabel="この速度以下のタイルの割合（%）", title="東京周辺とジュバ周辺の観測タイルの速度")
    ax.set_xscale("log")
    ax.grid(alpha=.25)
    ax.legend(loc="lower right")
    fig.text(.08, .01, "Speedtest by Ookla 2024年第2四半期、2026-11-11取得。1タイル1票、未観測は含まない。CC BY-NC-SA 4.0", fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(OUT / "capital_speed_comparison.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--places", type=Path, required=True)
    args = parser.parse_args()
    run(args.data, args.places)
