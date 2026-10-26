"""Compute the four within-mesh population allocations and their rankings.

Run from repository root with the analysis venv:
  /tmp/venv-geoai/bin/python projects/elderly-transit-100m-allocation/scripts/compute_allocations.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.name
OUTPUT = PROJECT / "outputs"

THRESHOLDS = {
    "main": (800.0, 1500.0),
    "tight": (500.0, 1000.0),
    "loose": (1000.0, 2000.0),
}
KEY_MESHES = ["53393610", "53394648", "53392558", "53394256", "53394207", "53393253"]


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (np.floating, np.integer)):
        return clean(float(value)) if isinstance(value, np.floating) else int(value)
    return value


def distance_to_nodes(tree, node_distance, points, max_snap_m):
    d, idx = tree.query(points, workers=8)
    out = np.full(len(points), np.nan)
    ok = np.isfinite(d) & (d <= max_snap_m)
    node = idx[ok]
    dist = node_distance[node].astype(float) + d[ok]
    good = np.isfinite(dist)
    out[np.flatnonzero(ok)[good]] = dist[good]
    return out, d


def add_point_distances(frame, lon_col, lat_col, tree, bus_d, rail_d, transformer):
    x, y = transformer.transform(frame[lon_col].to_numpy(), frame[lat_col].to_numpy())
    points = np.column_stack([x, y])
    out = {}
    for snap in (500, 200):
        bus, _ = distance_to_nodes(tree, bus_d, points, snap)
        rail, _ = distance_to_nodes(tree, rail_d, points, snap)
        out[f"bus_{snap}"] = bus
        out[f"rail_{snap}"] = rail
        out[f"snap_{snap}_m"] = np.nan  # filled below from the same query
    # Record the actual snapping distance for the 500 m primary.
    _, raw = tree.query(points, workers=8)
    out["nearest_node_m"] = raw
    return out


def ranking(frame, column):
    d = frame[frame[column].notna() & (frame[column] > 0)]
    return d.sort_values([column, "mesh"], ascending=[False, True])


def top_codes(frame, column, n=10):
    return ranking(frame, column)["mesh"].head(n).tolist()


def summarize(frame, columns, label):
    top = {name: top_codes(frame, col) for name, col in columns.items()}
    totals = {name: float(frame[col].sum()) for name, col in columns.items()}
    counts = {name: int((frame[col] > 0).sum()) for name, col in columns.items()}
    overlaps = {}
    for a, ca in columns.items():
        for b, cb in columns.items():
            overlaps[f"{a}__{b}"] = len(set(top[a]) & set(top[b]))
    spearman = {}
    complete = frame[[c for c in columns.values()]].dropna()
    for a, ca in columns.items():
        for b, cb in columns.items():
            if len(complete) >= 3:
                spearman[f"{a}__{b}"] = float(spearmanr(complete[ca], complete[cb]).statistic)
            else:
                spearman[f"{a}__{b}"] = None
    positions = {}
    for mesh in KEY_MESHES:
        row = frame[frame["mesh"] == mesh]
        positions[mesh] = {}
        for name, col in columns.items():
            if row.empty or pd.isna(row.iloc[0][col]) or row.iloc[0][col] <= 0:
                positions[mesh][name] = None
            else:
                ordered = ranking(frame, col)["mesh"].tolist()
                positions[mesh][name] = ordered.index(mesh) + 1 if mesh in ordered else None
    result = {
        "label": label,
        "top10": top,
        "totals": totals,
        "positive_meshes": counts,
        "overlaps": overlaps,
        "spearman": spearman,
        "key_mesh_positions": positions,
        "top10_intersection_all": sorted(
            set.intersection(*[set(v) for v in top.values()])
        ),
        "top10_in_at_least_3": sorted(
            [code for code in set().union(*[set(v) for v in top.values()])
             if sum(code in set(v) for v in top.values()) >= 3]
        ),
    }
    return result


def main():
    meshes = pd.read_parquet(ARTIFACTS / "meshes.parquet")
    wpop_mesh = pd.read_parquet(ARTIFACTS / "worldpop-mesh.parquet")
    meshes = meshes.merge(
        wpop_mesh[
            ["mesh", "pixels_inside", "pixels_full", "valid_pixels", "nodata_pixels",
             "zero_pixels", "positive_pixels", "wpop_sum", "wpop_census_ratio"]
        ],
        on="mesh",
        how="left",
    )

    net = np.load(ARTIFACTS / "network.npz")
    positions = net["positions"]
    bus_d = net["bus_m"]
    rail_d = net["rail_m"]
    tree = cKDTree(positions)
    transformer = Transformer.from_crs(4326, 6677, always_xy=True)

    # Point allocations (centre and five points).
    points = meshes[["mesh", "lon", "lat"]].copy()
    points["point_type"] = "center"
    quarters = pd.read_parquet(ARTIFACTS / "quarter-points.parquet")
    quarters["point_type"] = "quarter"
    point_frame = pd.concat(
        [points, quarters[["mesh", "lon", "lat", "point_type"]]], ignore_index=True
    )
    dists = add_point_distances(point_frame, "lon", "lat", tree, bus_d, rail_d, transformer)
    for key, values in dists.items():
        point_frame[key] = values

    for name, (bus_t, rail_t) in THRESHOLDS.items():
        for snap in (500, 200):
            gap = (
                (point_frame[f"bus_{snap}"] > bus_t)
                & (point_frame[f"rail_{snap}"] > rail_t)
            ).astype(float)
            gap[point_frame[f"bus_{snap}"].isna() | point_frame[f"rail_{snap}"].isna()] = np.nan
            point_frame[f"gap_{name}_{snap}"] = gap
    point_frame.to_parquet(ARTIFACTS / "point-access.parquet", index=False)

    center = point_frame[point_frame["point_type"] == "center"].set_index("mesh")
    for name in THRESHOLDS:
        for snap in (500, 200):
            col = f"gap_{name}_{snap}"
            values = center[col].reindex(meshes["mesh"]).to_numpy(dtype=float)
            meshes[f"center_gap_{name}_{snap}"] = values
            meshes[f"center_age65_{name}_{snap}"] = np.where(
                np.isnan(values), np.nan, meshes["age65"] * values
            )
            meshes[f"center_age75_{name}_{snap}"] = np.where(
                np.isnan(values), np.nan, meshes["age75"] * values
            )

    quarter = point_frame[point_frame["point_type"] == "quarter"]
    for name in THRESHOLDS:
        for snap in (500, 200):
            col = f"gap_{name}_{snap}"
            q = quarter.groupby("mesh")[col].agg(["mean", "count", "size"])
            q = q.reindex(meshes["mesh"])
            center_values = center[col].reindex(meshes["mesh"]).to_numpy(dtype=float)
            qmean = q["mean"].fillna(0).to_numpy(dtype=float)
            qcount = q["count"].fillna(0).to_numpy(dtype=float)
            qsize = q["size"].fillna(0).to_numpy(dtype=float)
            # Pre-registered rule: mean over the reachable points (centre + quadrants).
            available = point_frame.groupby("mesh")[col].agg(["mean", "count"])
            available = available.reindex(meshes["mesh"])
            fraction_available = available["mean"].to_numpy(dtype=float)
            # Conservative variant: require the centre and every existing quadrant to be known.
            fraction_allvalid = np.full(len(meshes), np.nan)
            center_ok = ~np.isnan(center_values)
            no_quarters = center_ok & (qsize == 0)
            all_quarters = center_ok & (qsize > 0) & (qcount == qsize)
            fraction_allvalid[no_quarters] = center_values[no_quarters]
            fraction_allvalid[all_quarters] = (
                center_values[all_quarters] + qmean[all_quarters] * qcount[all_quarters]
            ) / (1 + qcount[all_quarters])
            meshes[f"five_fraction_{name}_{snap}"] = fraction_available
            meshes[f"five_fraction_allvalid_{name}_{snap}"] = fraction_allvalid
            meshes[f"five_points_{name}_{snap}"] = available["count"].fillna(0).to_numpy(dtype=float)
            meshes[f"five_age65_{name}_{snap}"] = meshes["age65"] * fraction_available
            meshes[f"five_age75_{name}_{snap}"] = meshes["age75"] * fraction_available
            meshes[f"five_age65_allvalid_{name}_{snap}"] = meshes["age65"] * fraction_allvalid

    # Pixel allocations.
    pixels = pd.read_parquet(ARTIFACTS / "worldpop-pixels.parquet")
    pixels = pixels[
        pixels["inside_mainland"] & pixels["in_mesh"]
        & pixels["mesh"].isin(set(meshes["mesh"]))
    ].copy()
    x, y = transformer.transform(pixels["lon"].to_numpy(), pixels["lat"].to_numpy())
    points_xy = np.column_stack([x, y])
    for snap in (500, 200):
        bus, bus_raw = distance_to_nodes(tree, bus_d, points_xy, snap)
        rail, rail_raw = distance_to_nodes(tree, rail_d, points_xy, snap)
        pixels[f"bus_{snap}"] = bus
        pixels[f"rail_{snap}"] = rail
        pixels[f"nearest_node_{snap}_m"] = bus_raw if snap == 500 else rail_raw
    pixels["positive"] = pixels["value"] > 0
    pixels["valid"] = pixels["status"] != "nodata"
    for name, (bus_t, rail_t) in THRESHOLDS.items():
        for snap in (500, 200):
            gap = (
                (pixels[f"bus_{snap}"] > bus_t) & (pixels[f"rail_{snap}"] > rail_t)
            ).astype(float)
            known = pixels[f"bus_{snap}"].notna() & pixels[f"rail_{snap}"].notna()
            gap[~known] = np.nan
            pixels[f"gap_{name}_{snap}"] = gap
    pixels.to_parquet(ARTIFACTS / "pixel-access.parquet", index=False)

    for name in THRESHOLDS:
        for snap in (500, 200):
            gap = pixels[f"gap_{name}_{snap}"]
            known = gap.notna() & pixels["valid"]
            positive = pixels["positive"]
            known_positive = positive & known
            index = pd.Index(sorted(set(meshes["mesh"])), name="mesh")
            weight_known = (
                pixels.loc[known_positive, "value"]
                .groupby(pixels.loc[known_positive, "mesh"])
                .sum()
                .reindex(index, fill_value=0.0)
            )
            weight_gap = (
                pixels.loc[known_positive & gap.fillna(False), "value"]
                .groupby(pixels.loc[known_positive & gap.fillna(False), "mesh"])
                .sum()
                .reindex(index, fill_value=0.0)
            )
            weight_positive = (
                pixels.loc[positive, "value"]
                .groupby(pixels.loc[positive, "mesh"])
                .sum()
                .reindex(index, fill_value=0.0)
            )
            uniform_known = (
                pixels.loc[known].groupby("mesh").size().reindex(index, fill_value=0)
            )
            uniform_gap = (
                pixels.loc[known & gap.fillna(False)].groupby("mesh").size()
                .reindex(index, fill_value=0)
            )
            stats = pd.DataFrame(index=index)
            stats["wpop_fraction"] = weight_gap / weight_known.where(weight_known > 0)
            stats["wpop_unknown_weight_share"] = (
                (weight_positive - weight_known) / weight_positive.where(weight_positive > 0)
            )
            stats["uniform_fraction"] = uniform_gap / uniform_known.where(uniform_known > 0)
            stats[f"known_pixels_{name}_{snap}"] = uniform_known
            stats[f"gap_pixels_{name}_{snap}"] = uniform_gap
            # NoData counts are mesh-level and already in meshes.
            nd = meshes.set_index("mesh")["nodata_pixels"].reindex(stats.index)
            stats[f"wpop_fraction_{name}_{snap}"] = stats["wpop_fraction"]
            stats[f"wpop_unknown_weight_share_{name}_{snap}"] = stats["wpop_unknown_weight_share"]
            stats[f"uniform_fraction_{name}_{snap}"] = stats["uniform_fraction"]
            stats[f"wpop_age65_{name}_{snap}"] = meshes.set_index("mesh")["age65"].reindex(stats.index) * stats["wpop_fraction"]
            stats[f"wpop_age75_{name}_{snap}"] = meshes.set_index("mesh")["age75"].reindex(stats.index) * stats["wpop_fraction"]
            stats[f"uniform_age65_{name}_{snap}"] = meshes.set_index("mesh")["age65"].reindex(stats.index) * stats["uniform_fraction"]
            stats[f"uniform_age75_{name}_{snap}"] = meshes.set_index("mesh")["age75"].reindex(stats.index) * stats["uniform_fraction"]
            # NoData variants for the main threshold and snap.
            if name == "main" and snap == 500:
                stats["wpop_strict_age65"] = np.where(
                    stats["wpop_unknown_weight_share"] > 0, np.nan, stats["wpop_age65_main_500"]
                )
                stats["wpop_nodata_uniform_age65"] = np.where(
                    nd > 0, stats["uniform_age65_main_500"], stats["wpop_age65_main_500"]
                )
                stats["wpop_exclude_nodata_age65"] = np.where(
                    nd > 0, np.nan, stats["wpop_age65_main_500"]
                )
            stats = stats.drop(columns=["wpop_fraction", "wpop_unknown_weight_share", "uniform_fraction"])
            stats = stats.reset_index()
            meshes = meshes.drop(columns=[c for c in stats.columns if c != "mesh" and c in meshes.columns], errors="ignore")
            meshes = meshes.merge(stats, on="mesh", how="left")

    # Ratio-restricted ranking.
    ratio_ok = meshes["wpop_census_ratio"].between(0.5, 2.0, inclusive="both")
    ratio_frame = meshes[ratio_ok].copy()

    summaries = {}
    summaries["main"] = summarize(
        meshes,
        {
            "center": "center_age65_main_500",
            "five": "five_age65_main_500",
            "wpop": "wpop_age65_main_500",
            "uniform": "uniform_age65_main_500",
        },
        "主: バス800m・駅1,500m、スナップ500m",
    )
    summaries["tight"] = summarize(
        meshes,
        {
            "center": "center_age65_tight_500",
            "five": "five_age65_tight_500",
            "wpop": "wpop_age65_tight_500",
            "uniform": "uniform_age65_tight_500",
        },
        "バス500m・駅1,000m",
    )
    summaries["loose"] = summarize(
        meshes,
        {
            "center": "center_age65_loose_500",
            "five": "five_age65_loose_500",
            "wpop": "wpop_age65_loose_500",
            "uniform": "uniform_age65_loose_500",
        },
        "バス1,000m・駅2,000m",
    )
    summaries["age75"] = summarize(
        meshes,
        {
            "center": "center_age75_main_500",
            "five": "five_age75_main_500",
            "wpop": "wpop_age75_main_500",
            "uniform": "uniform_age75_main_500",
        },
        "75歳以上、主閾値",
    )
    summaries["five_conservative"] = summarize(
        meshes,
        {"five": "five_age65_allvalid_main_500"},
        "5点の保守的扱い（中心と既存の全象限が既知のメッシュだけ）",
    )
    summaries["snap200"] = summarize(
        meshes,
        {
            "center": "center_age65_main_200",
            "five": "five_age65_main_200",
            "wpop": "wpop_age65_main_200",
            "uniform": "uniform_age65_main_200",
        },
        "需要点スナップ200m",
    )
    summaries["nodata_variants"] = {
        "main": summarize(meshes, {"wpop": "wpop_age65_main_500"}, "NoDataを有効画素で再正規化"),
        "strict": summarize(meshes, {"wpop": "wpop_strict_age65"}, "未知の重みを厳格に除外"),
        "nodata_uniform": summarize(meshes, {"wpop": "wpop_nodata_uniform_age65"}, "NoDataがあるメッシュは一様"),
        "exclude_nodata": summarize(meshes, {"wpop": "wpop_exclude_nodata_age65"}, "NoDataがあるメッシュを除外"),
    }
    summaries["ratio_restricted"] = summarize(
        ratio_frame,
        {
            "center": "center_age65_main_500",
            "wpop": "wpop_age65_main_500",
        },
        "WorldPop/国勢調査比0.5〜2.0",
    )

    meshes.to_parquet(ARTIFACTS / "mesh-allocations.parquet", index=False)
    summary = {
        "thresholds_m": THRESHOLDS,
        "snap_m": {"primary": 500, "sensitivity": 200},
        "input": {
            "meshes": int(len(meshes)),
            "age65_known": int(meshes["age65"].notna().sum()),
            "age65_suppressed": int(meshes["age65"].isna().sum()),
            "pixels_used": int(len(pixels)),
            "pixels_positive": int((pixels["value"] > 0).sum()),
            "pixels_known_access": int(pixels["bus_500"].notna().sum()),
            "pixels_unknown_access_positive": int(
                ((pixels["value"] > 0) & pixels["bus_500"].isna()).sum()
            ),
            "meshes_no_positive_weight": int(
                (meshes["wpop_age65_main_500"].isna() & meshes["age65"].notna()).sum()
            ),
            "meshes_unknown_weight_share_gt_5pct": int(
                (meshes["wpop_unknown_weight_share_main_500"] > 0.05).sum()
            ),
        },
        "summaries": summaries,
    }
    summary = clean(summary)
    (OUTPUT / "allocations-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
