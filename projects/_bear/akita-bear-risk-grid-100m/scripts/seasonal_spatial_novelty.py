"""Spatial novelty of fixed Apr–Sep positive bear-report cells; no model fitting.

From the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/seasonal_spatial_novelty.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/_bear/akita-bear-risk-grid-100m \
      projects/_bear/akita-bear-risk-grid-100m/outputs/apr_sep_spatial_novelty.json
"""

import argparse
import json
from pathlib import Path

import numpy as np
import scipy
from scipy.spatial import cKDTree

from grid import Grid
import labels as lb
import same_year_spatial_oof as spatial
from seasonal_transfer_b_env import seasonal_labels

YEARS = (2023, 2024, 2025, 2026)
COMPARISONS = ((2025, (2023, 2024)), (2026, (2023, 2024, 2025)))
DISTANCES_M = (100, 300, 500, 1000)
LABEL_KEYS = ("positive_cells", "inside_window_reports", "outside_window_reports")


def past_union(positives, years):
    if not years:
        raise ValueError("past years must be non-empty")
    first = np.asarray(positives[years[0]])
    if first.ndim != 2 or first.dtype != bool:
        raise ValueError("past cell masks must be 2-D boolean arrays")
    combined = first.copy()
    for year in years[1:]:
        arr = np.asarray(positives[year])
        if arr.shape != first.shape or arr.dtype != bool:
            raise ValueError("past cell masks must have the same shape and boolean type")
        combined |= arr
    return combined


def summarize(target, past, *, cell_size_m):
    """Centre-to-centre Euclidean EPSG:6678 distances on the original grid."""
    target, past = np.asarray(target), np.asarray(past)
    if target.ndim != 2 or target.shape != past.shape or target.dtype != bool or past.dtype != bool:
        raise ValueError("aligned 2-D boolean masks are required")
    if cell_size_m <= 0 or not target.any() or not past.any():
        raise ValueError("cell size and both positive sets must be non-empty")
    target_points = np.column_stack(np.nonzero(target))
    past_points = np.column_stack(np.nonzero(past))
    distances = cKDTree(past_points).query(target_points)[0] * cell_size_m
    same = int(np.count_nonzero(target & past))
    if int(np.count_nonzero(distances == 0)) != same:
        raise ValueError("zero-distance count disagrees with exact cell overlap")
    n = int(target.sum())
    return {"n_target_positive": n, "n_past_union_positive": int(past.sum()),
            "same_cell": {"count": same, "share": same / n},
            "nearest_distance_m": {"median": float(np.median(distances)),
                                   "p90": float(np.percentile(distances, 90))},
            "within_distance_m": {str(limit): {"count": int(np.count_nonzero(distances <= limit)),
                                               "share": float(np.mean(distances <= limit))}
                                  for limit in DISTANCES_M}}


def main():
    import duckdb
    import pyproj

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("art", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("output already exists; refusing post-result replacement")
    project = Path(__file__).resolve().parents[1]
    previous_path = project / "outputs/apr_sep_year_pool_b_env.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    if previous["setup"]["source"] != lb.SIGHTING:
        raise ValueError("fixed sighting source changed")
    fixed_files = ("grid_mask.npz", "reports_by_year.npz", "cells.parquet",
                   "worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz")
    hashes = {name: spatial.sha256(args.art / name) for name in fixed_files}
    if hashes != previous["setup"]["fixed_input_sha256"]:
        raise ValueError("fixed source artifacts changed")
    grid_path = args.art / "grid.json"
    meta = json.loads(grid_path.read_text(encoding="utf-8"))
    if spatial.sha256(grid_path) != previous["setup"]["grid_json_sha256"] \
            or meta["crs"] != "EPSG:6678" or meta["size"] != 100:
        raise ValueError("fixed EPSG:6678 100m grid changed")
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(args.art / "grid_mask.npz") as masked:
        muni = masked["muni"]
    if muni.shape != (grid.ny, grid.nx) or int((muni >= 0).sum()) != previous["setup"]["n_cells"]:
        raise ValueError("prefecture cell mask differs from previous run")
    with np.load(args.art / "reports_by_year.npz") as reports:
        known_full = {year: reports[f"c{year}"] for year in YEARS}

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2023-04-01", "2026-10-01"]).fetchnumpy()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = transformer.transform(raw["longitude"], raw["latitude"])
    counts, label_info = seasonal_labels(grid, muni, x, y, raw["observed_at"], known_full, years=YEARS)
    for year in YEARS:
        for key in LABEL_KEYS:
            if label_info[year][key] != previous["labels"][str(year)][key]:
                raise ValueError(f"{year} seasonal {key} differs from previous fixed run")
    positives = {year: counts[year] > 0 for year in YEARS}
    results = {}
    for target_year, past_years in COMPARISONS:
        key = f"{target_year}_vs_{'_'.join(map(str, past_years))}"
        results[key] = {"target_year": target_year, "past_years": list(past_years),
                        **summarize(positives[target_year], past_union(positives, past_years),
                                    cell_size_m=grid.size)}
        print(key, results[key], flush=True)
    first = results["2025_vs_2023_2024"]
    second = results["2026_vs_2023_2024_2025"]
    comparison = {"same_cell_share_2026_minus_2025": second["same_cell"]["share"] - first["same_cell"]["share"],
                  "nearest_median_m_2026_minus_2025": second["nearest_distance_m"]["median"] - first["nearest_distance_m"]["median"],
                  "nearest_p90_m_2026_minus_2025": second["nearest_distance_m"]["p90"] - first["nearest_distance_m"]["p90"],
                  "within_share_2026_minus_2025": {str(d): second["within_distance_m"][str(d)]["share"] - first["within_distance_m"][str(d)]["share"]
                                                   for d in DISTANCES_M}}
    output = {"mode": "exploratory descriptive spatial novelty audit; no fitting",
              "definition": {"positive": "at least one fixed-source bear report in the same Apr–Sep 100m cell",
                             "past": "union of distinct Apr–Sep positive cells in the named earlier years",
                             "distance": "nearest past positive cell centre, Euclidean EPSG:6678 metres; exact same cell is 0m",
                             "within_inclusive_thresholds_m": list(DISTANCES_M),
                             "denominator": "target-year Apr–Sep positive cells"},
              "setup": {"source": lb.SIGHTING, "grid_json_sha256": spatial.sha256(grid_path),
                        "fixed_input_sha256": hashes, "previous_pool_json_sha256": spatial.sha256(previous_path),
                        "numpy_version": np.__version__, "scipy_version": scipy.__version__,
                        "script": "projects/_bear/akita-bear-risk-grid-100m/scripts/seasonal_spatial_novelty.py"},
              "labels": label_info, "comparisons": results, "between_target_years": comparison,
              "limitations": ["2026 past union includes one more year than the 2025 past union, mechanically favouring shorter distances and more overlap",
                              "reported coordinates can be approximate and reporting effort varies; distance is not road distance",
                              "spatial novelty alone does not identify why predictive capture changed"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
