"""Audit fixed B_env feature distributions for Apr–Sep positive cells, without fitting.

From repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/seasonal_positive_shift.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/_bear/akita-bear-risk-grid-100m \
      projects/_bear/akita-bear-risk-grid-100m/outputs/apr_sep_positive_feature_shift.json
"""

import argparse
import json
from pathlib import Path

import numpy as np
import scipy

import features as ft
from grid import Grid
import labels as lb
import positive_feature_audit as feature_audit
import same_year_spatial_oof as spatial
from seasonal_transfer_b_env import seasonal_labels
from seasonal_pool_b_env import verify_previous_labels

YEARS = (2024, 2025, 2026)
PAIRS = ((2024, 2025), (2025, 2026))
DELTA = "cliffs_delta_later_minus_earlier"


def compare_feature(earlier, later):
    """Finite-only descriptive comparison; positive delta means later tends higher."""
    raw = feature_audit.summarize_feature(later, earlier)
    return {"earlier": raw["missed"], "later": raw["captured"],
            "median_later_minus_earlier": raw["captured_minus_missed_median"],
            "cliffs_delta_later_minus_earlier": raw["cliffs_delta"],
            "ks_statistic": raw["ks_statistic"]}


def audit_pair(features, earlier_positive, later_positive):
    earlier_positive = np.asarray(earlier_positive)
    later_positive = np.asarray(later_positive)
    if earlier_positive.ndim != 1 or later_positive.shape != earlier_positive.shape \
            or earlier_positive.dtype != bool or later_positive.dtype != bool \
            or not features:
        raise ValueError("feature values and positive labels must be aligned")
    n = len(earlier_positive)
    result = {}
    for name, values in features.items():
        arr = np.asarray(values)
        if arr.shape != (n,):
            raise ValueError(f"feature {name} is not aligned with labels")
        result[name] = {"unit": feature_audit.feature_unit(name),
                        **compare_feature(arr[earlier_positive], arr[later_positive])}
    return {"earlier_positive_cells": int(earlier_positive.sum()),
            "later_positive_cells": int(later_positive.sum()), "features": result}


def rank_shifts(pairs):
    keys = ("2024_to_2025", "2025_to_2026")
    if set(pairs) != set(keys):
        raise ValueError("expected exactly two adjacent-year comparisons")
    earlier, later = (pairs[key]["features"] for key in keys)
    if set(earlier) != set(later):
        raise ValueError("feature sets differ across comparisons")
    top = {}
    for key in keys:
        rows = [{"feature": name, "cliffs_delta": entry[DELTA],
                 "abs_cliffs_delta": abs(entry[DELTA]), "ks_statistic": entry.get("ks_statistic")}
                for name, entry in pairs[key]["features"].items() if entry[DELTA] is not None]
        top[key] = sorted(rows, key=lambda row: (-row["abs_cliffs_delta"], row["feature"]))[:5]
    contrast = []
    for name in earlier:
        a, b = earlier[name][DELTA], later[name][DELTA]
        if a is None or b is None:
            continue
        contrast.append({"feature": name, "delta_2024_to_2025": a,
                         "delta_2025_to_2026": b,
                         "abs_delta_2024_to_2025": abs(a),
                         "abs_delta_2025_to_2026": abs(b),
                         "increase_abs_delta": abs(b) - abs(a)})
    contrast.sort(key=lambda row: (-row["increase_abs_delta"], row["feature"]))
    return {"top5_by_pair": top,
            "greater_in_2025_to_2026": [row for row in contrast if row["increase_abs_delta"] > 0],
            "both_pair_deltas": sorted(contrast, key=lambda row: row["feature"])}


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
    previous_path = project / "outputs/apr_sep_year_transfer_b_env.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    if previous["setup"]["source"] != lb.SIGHTING:
        raise ValueError("fixed sighting source changed")
    fixed_files = ("grid_mask.npz", "reports_by_year.npz", "cells.parquet",
                   "worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz")
    hashes = {name: spatial.sha256(args.art / name) for name in fixed_files}
    if hashes != previous["setup"]["fixed_input_sha256"]:
        raise ValueError("fixed grid, label or feature inputs changed")
    grid_path = args.art / "grid.json"
    meta = json.loads(grid_path.read_text(encoding="utf-8"))
    if spatial.sha256(grid_path) != previous["setup"]["grid_json_sha256"] \
            or meta["crs"] != "EPSG:6678" or meta["size"] != 100:
        raise ValueError("fixed 100m grid changed")
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(args.art / "grid_mask.npz") as mask:
        muni = mask["muni"]
    inside = muni >= 0
    if int(inside.sum()) != previous["setup"]["n_cells"]:
        raise ValueError("prefecture cell count changed")
    with np.load(args.art / "reports_by_year.npz") as saved:
        known = {year: saved[f"c{year}"] for year in YEARS}
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2024-04-01", "2026-10-01"]).fetchnumpy()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = transformer.transform(raw["longitude"], raw["latitude"])
    counts, info = seasonal_labels(grid, muni, x, y, raw["observed_at"], known, years=YEARS)
    verify_previous_labels(info, previous)
    positives = {year: counts[year][inside] > 0 for year in YEARS}
    print("fixed 2024–2026 seasonal positives reconciled:",
          {year: int(positives[year].sum()) for year in YEARS}, flush=True)
    with np.load(args.art / "worldcover.npz") as wc, np.load(args.art / "dem.npz") as dem, \
            np.load(args.art / "worldpop.npz") as pop, np.load(args.art / "osm.npz") as osm:
        static = ft.static_features(wc, dem, pop, osm)
    if list(static) != previous["setup"]["feature_names"] or len(static) != 28:
        raise ValueError("the 28 existing B_env features changed")
    values = {name: arr[inside] for name, arr in static.items()}
    del static
    comparisons = {f"{earlier}_to_{later}": audit_pair(values, positives[earlier], positives[later])
                   for earlier, later in PAIRS}
    ranked = rank_shifts(comparisons)
    output = {"mode": "descriptive positive-cell feature shift audit; no fitting or p-values",
              "definition": {"positive": "at least one fixed-source bear report in Apr 1–Sep 30; same 100m cell rule",
                             "yearly_distribution": "static feature values among that year's positive cells only",
                             "quantiles": "finite values only; nonfinite counted as missing and never imputed",
                             "cliffs_delta": "2*U(later,earlier)/(n_later_valid*n_earlier_valid)-1; positive means later tends higher",
                             "ks": "two-sample KS statistic, no p-value decision",
                             "top5": "descending abs(Cliff's delta), feature name tie-break"},
              "setup": {"source": lb.SIGHTING, "grid_json_sha256": spatial.sha256(grid_path),
                        "fixed_input_sha256": hashes,
                        "previous_transfer_json_sha256": spatial.sha256(previous_path),
                        "feature_names": list(values), "numpy_version": np.__version__,
                        "scipy_version": scipy.__version__,
                        "script": "projects/_bear/akita-bear-risk-grid-100m/scripts/seasonal_positive_shift.py"},
              "labels": info, "comparisons": comparisons, "summary": ranked,
              "limitations": ["feature surfaces are fixed; differences describe which cells became positive, not temporal changes in those surfaces",
                              "correlated features and reporting/position biases may affect shifts",
                              "distribution shift alone does not establish why predictive capture changed"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("top5:", ranked["top5_by_pair"], flush=True)


if __name__ == "__main__":
    main()
