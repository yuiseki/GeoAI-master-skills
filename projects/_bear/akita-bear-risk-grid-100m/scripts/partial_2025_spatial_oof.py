"""One fixed 2025 Apr–Sep B_env spatial OOF run; compare existing full/partial years.

From the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/partial_2025_spatial_oof.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/_bear/akita-bear-risk-grid-100m \
      projects/_bear/akita-bear-risk-grid-100m/outputs/b2_2025_apr_sep_spatial_oof.json \
      artifacts/_bear/akita-bear-risk-grid-100m/eval/b2_2025_apr_sep_spatial_oof_scores.npz
"""

import argparse
import json
from pathlib import Path

import numpy as np

import features as ft
from grid import Grid
import labels as lb
import model_eval as me
import same_year_spatial_oof as spatial
from fold_local_oof_audit import load_original_folds

WINDOW_START = np.datetime64("2025-04-01T00:00", "m")
WINDOW_END = np.datetime64("2025-10-01T00:00", "m")
FISCAL_END = np.datetime64("2026-04-01T00:00", "m")


def seasonal_counts(grid, muni, x, y, observed_at, existing_full):
    """Use the original point-to-cell convention and reconcile the full 2025 FY."""
    dates = np.asarray(observed_at, dtype="datetime64[m]")
    x, y = np.asarray(x), np.asarray(y)
    if dates.ndim != 1 or x.shape != dates.shape or y.shape != dates.shape \
            or np.isnat(dates).any() or np.any((dates < WINDOW_START) | (dates >= FISCAL_END)):
        raise ValueError("source rows must all be dated within 2025 fiscal year")
    if existing_full.shape != muni.shape:
        raise ValueError("full-year label shape differs from grid")
    years = lb.bear_year(dates)
    full_counts, full_off = lb.counts_by_year(grid, muni, x, y, years, [2025])
    full = full_counts[2025]
    if not np.array_equal(full, existing_full):
        raise ValueError("source full-year cell counts differ from saved c2025 label")
    chosen = dates < WINDOW_END
    partial_counts, off = lb.counts_by_year(grid, muni, x[chosen], y[chosen], years[chosen], [2025])
    partial = partial_counts[2025]
    inside = muni >= 0
    if np.any(partial > full) or int(partial[inside].sum()) + off[2025] != int(chosen.sum()):
        raise ValueError("partial-year counts are not a subset of full-year labels")
    info = {"window_start_inclusive": str(WINDOW_START), "window_end_exclusive": str(WINDOW_END),
            "n_full_reports": int(len(dates)), "n_full_outside_prefecture_cells": full_off[2025],
            "n_full_inside_reports": int(full[inside].sum()),
            "n_window_reports": int(chosen.sum()),
            "n_window_outside_prefecture_cells": off[2025],
            "n_window_inside_reports": int(partial[inside].sum()),
            "n_window_positive_cells": int((partial[inside] > 0).sum())}
    return partial, info


def main():
    import duckdb
    import pyproj
    import sklearn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("art", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("scores_out", type=Path)
    args = parser.parse_args()
    if args.out.exists() or args.scores_out.exists():
        raise ValueError("one-run outputs already exist; refusing a second model run")
    project = Path(__file__).resolve().parents[1]
    old_path = project / "outputs/b2_b3_same_year_spatial_oof.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    setup = old["setup"]
    if setup["hgb"] != me.HGB or setup["random_state"] != 0 \
            or setup["sklearn_version"] != sklearn.__version__ \
            or setup["splitter"] != "GroupKFold(n_splits=5, shuffle=False)":
        raise ValueError("B_env HGB, seed, splitter or library version differs from old OOF")
    relevant = ("grid_mask.npz", "reports_by_year.npz", "cells.parquet",
                "worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz")
    hashes = {name: spatial.sha256(args.art / name) for name in relevant}
    if any(hashes[name] != setup["input_sha256"][name] for name in relevant):
        raise ValueError("fixed input arrays or cells table differ from old OOF")
    grid_path = args.art / "grid.json"
    meta = json.loads(grid_path.read_text(encoding="utf-8"))
    if meta["crs"] != "EPSG:6678" or meta["size"] != 100:
        raise ValueError("original grid CRS or cell size changed")
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(args.art / "grid_mask.npz") as masked:
        muni = masked["muni"]
    inside = muni >= 0
    if int(inside.sum()) != old["years"]["B2"]["n_cells"]:
        raise ValueError("prefecture cell count changed")
    fold_path = project / "outputs/b2_b3_same_year_spatial_oof_folds.csv"
    _, saved_fold = load_original_folds(args.art / "grid_mask.npz", fold_path, old)
    iy, ix = np.nonzero(inside)
    blocks, fold = spatial.fixed_folds(ix, iy)
    if not np.array_equal(fold, saved_fold) or len(np.unique(blocks)) != setup["n_blocks"]:
        raise ValueError("spatial fold assignment differs from original OOF")
    with np.load(args.art / "reports_by_year.npz") as known:
        existing_full = known["c2025"]
    if int((existing_full[inside] > 0).sum()) != old["years"]["B2"]["n_positive"]:
        raise ValueError("saved full-year label count differs from original OOF")

    # Same frozen source, species and coordinate transformation as labels.py.
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at
                         FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", str(WINDOW_START), str(FISCAL_END)]).fetchnumpy()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = transformer.transform(raw["longitude"], raw["latitude"])
    counts, label_info = seasonal_counts(grid, muni, x, y, raw["observed_at"], existing_full)
    positive = counts[inside] > 0
    print("2025 Apr-Sep labels:", label_info, flush=True)

    with np.load(args.art / "worldcover.npz") as wc, np.load(args.art / "dem.npz") as dem, \
            np.load(args.art / "worldpop.npz") as pop, np.load(args.art / "osm.npz") as osm:
        static = ft.static_features(wc, dem, pop, osm)
    names = list(static)
    if names != setup["feature_names"] or len(names) != 28:
        raise ValueError("B_env static features differ from original OOF")
    X = np.column_stack([static[name][inside] for name in names]).astype(np.float32)
    del static
    scores, diagnostics = spatial.oof_scores(X, positive, blocks, fold)
    result_metrics = spatial.score_metrics(scores, positive)
    comparison = {"2025_full_fiscal_year": {
                      "positive_cells": old["years"]["B2"]["n_positive"],
                      **{key: old["years"]["B2"]["same_year_spatial_oof"][key] for key in spatial.METRICS}},
                  "2025_apr_sep": {"positive_cells": int(positive.sum()), **result_metrics},
                  "2026_apr_sep": {
                      "positive_cells": old["years"]["B3"]["n_positive"],
                      **{key: old["years"]["B3"]["same_year_spatial_oof"][key] for key in spatial.METRICS}}}
    args.scores_out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.scores_out, scores=scores)
    output = {"mode": "exploratory same-year spatial OOF diagnostic; not a deployable forecast",
              "label": label_info,
              "setup": {"source": lb.SIGHTING, "source_revision": "c7047ab442ea3471aaa52af6e56a966ac768ff61",
                        "grid_json_sha256": spatial.sha256(grid_path), "fixed_input_sha256": hashes,
                        "old_oof_json_sha256": spatial.sha256(old_path),
                        "folds_csv_sha256": spatial.sha256(fold_path),
                        "feature_names": names, "hgb": me.HGB, "random_state": 0,
                        "sklearn_version": sklearn.__version__, "n_cells": len(positive),
                        "n_blocks": len(np.unique(blocks)), "n_folds": 5,
                        "scores_npz": str(args.scores_out),
                        "scores_npz_sha256": spatial.sha256(args.scores_out)},
              "fold_diagnostics_2025_apr_sep": diagnostics,
              "comparison": comparison,
              "capture@5%_2025_partial_minus_2025_full": (
                  comparison["2025_apr_sep"]["capture@5%"] - comparison["2025_full_fiscal_year"]["capture@5%"]),
              "capture@5%_2025_partial_minus_2026_partial": (
                  comparison["2025_apr_sep"]["capture@5%"] - comparison["2026_apr_sep"]["capture@5%"]),
              "limitations": ["labels are reported locations, not exact bear locations; observation effort can vary by year",
                              "2025 full fiscal year includes October 2025-March 2026; window labels are a subset",
                              "same-year spatial OOF is descriptive and not a future-year forecast",
                              "2025 vs 2026 differences cannot isolate the causal effect of seasonal-window length"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("capture@5%:", {name: row["capture@5%"] for name, row in comparison.items()}, flush=True)


if __name__ == "__main__":
    main()
