"""Two prespecified Apr–Sep B_env pooling runs, using one frozen sighting source.

From the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/seasonal_pool_b_env.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/_bear/akita-bear-risk-grid-100m \
      projects/_bear/akita-bear-risk-grid-100m/outputs/apr_sep_year_pool_b_env.json
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
from seasonal_transfer_b_env import seasonal_labels

YEARS = (2023, 2024, 2025, 2026)
RUNS = (((2023, 2024), 2025), ((2023, 2024, 2025), 2026))
LABEL_KEYS = ("positive_cells", "inside_window_reports", "outside_window_reports")


def verify_previous_labels(info, previous):
    for year in (2024, 2025, 2026):
        for key in LABEL_KEYS:
            if info[year][key] != previous["labels"][str(year)][key]:
                raise ValueError(f"{year} seasonal labels differ on {key}")


def fit_pooled(X, labels, train_years, model_factory=None):
    """Stack the identical static cell rows by year; no year feature or weights."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    X = np.asarray(X)
    if X.ndim != 2 or X.shape[1] != 28 or not train_years:
        raise ValueError("expected fixed 28-feature design and nonempty training years")
    for year in train_years:
        y = np.asarray(labels[year])
        if y.shape != (len(X),) or y.dtype != bool:
            raise ValueError(f"invalid {year} training labels")
    Xtr = np.vstack([X for _ in train_years])
    ytr = np.concatenate([labels[year] for year in train_years])
    if np.unique(ytr).size != 2:
        raise ValueError("pooled training labels lack a class")
    model = (model_factory() if model_factory is not None else
             HistGradientBoostingClassifier(**me.HGB, random_state=0))
    model.fit(Xtr, ytr)
    scores = np.asarray(model.predict_proba(X)[:, 1], dtype=np.float64)
    if scores.shape != (len(X),) or not np.isfinite(scores).all():
        raise ValueError("invalid pooled prediction scores")
    return scores, len(ytr), int(ytr.sum())


def main():
    import duckdb
    import pyproj
    import sklearn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("art", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("one-run output already exists; refusing additional exploration")
    project = Path(__file__).resolve().parents[1]
    old_path = project / "outputs/b2_b3_same_year_spatial_oof.json"
    previous_path = project / "outputs/apr_sep_year_transfer_b_env.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    setup = old["setup"]
    if setup["hgb"] != me.HGB or setup["random_state"] != 0 \
            or setup["sklearn_version"] != sklearn.__version__ \
            or previous["setup"]["source"] != lb.SIGHTING:
        raise ValueError("HGB, seed, library or source differ from fixed runs")
    for key in ("2024_to_2025", "2025_to_2026"):
        if key not in previous["runs"]:
            raise ValueError("prior seasonal single-year comparator missing")
    relevant = ("grid_mask.npz", "reports_by_year.npz", "cells.parquet",
                "worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz")
    hashes = {name: spatial.sha256(args.art / name) for name in relevant}
    if any(hashes[name] != setup["input_sha256"][name] or
           hashes[name] != previous["setup"]["fixed_input_sha256"][name] for name in relevant):
        raise ValueError("fixed input array hash changed")
    grid_path = args.art / "grid.json"
    meta = json.loads(grid_path.read_text(encoding="utf-8"))
    if meta["crs"] != "EPSG:6678" or meta["size"] != 100 \
            or spatial.sha256(grid_path) != previous["setup"]["grid_json_sha256"]:
        raise ValueError("fixed grid changed")
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(args.art / "grid_mask.npz") as mask:
        muni = mask["muni"]
    inside = muni >= 0
    if int(inside.sum()) != previous["setup"]["n_cells"]:
        raise ValueError("prefecture cell count changed")
    with np.load(args.art / "reports_by_year.npz") as reports:
        known = {year: reports[f"c{year}"] for year in YEARS}

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2023-04-01", "2026-10-01"]).fetchnumpy()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = transformer.transform(raw["longitude"], raw["latitude"])
    counts, info = seasonal_labels(grid, muni, x, y, raw["observed_at"], known, years=YEARS)
    verify_previous_labels(info, previous)
    print("all four fiscal labels reconciled:", info, flush=True)
    with np.load(args.art / "worldcover.npz") as wc, np.load(args.art / "dem.npz") as dem, \
            np.load(args.art / "worldpop.npz") as pop, np.load(args.art / "osm.npz") as osm:
        static = ft.static_features(wc, dem, pop, osm)
    names = list(static)
    if names != setup["feature_names"] or names != previous["setup"]["feature_names"] \
            or len(names) != 28:
        raise ValueError("B_env feature names changed")
    X = np.column_stack([static[name][inside] for name in names]).astype(np.float32)
    del static
    labels = {year: counts[year][inside] > 0 for year in YEARS}
    runs = {}
    for train_years, test_year in RUNS:
        scores, n_rows, n_positive = fit_pooled(X, labels, train_years)
        result_metrics = spatial.score_metrics(scores, labels[test_year])
        key = "_".join(map(str, train_years)) + f"_to_{test_year}"
        comparator_key = f"{test_year - 1}_to_{test_year}"
        reference = previous["runs"][comparator_key]
        runs[key] = {"train_years": train_years, "test_year": test_year,
                     "train_rows": n_rows, "train_positive_rows": n_positive,
                     "train_positive_by_year": {str(year): int(labels[year].sum()) for year in train_years},
                     "test_positive_cells": int(labels[test_year].sum()),
                     **result_metrics,
                     "single_year_comparator": comparator_key,
                     "single_year_capture@5%": reference["capture@5%"],
                     "capture@5%_minus_single_year": result_metrics["capture@5%"] - reference["capture@5%"]}
        print(key, runs[key], flush=True)
    output = {"mode": "exploratory Apr-Sep multi-year pooling; two fixed runs only",
              "setup": {"source": lb.SIGHTING, "grid_json_sha256": spatial.sha256(grid_path),
                        "fixed_input_sha256": hashes, "previous_transfer_json_sha256": spatial.sha256(previous_path),
                        "previous_oof_json_sha256": spatial.sha256(old_path),
                        "feature_names": names, "hgb": me.HGB, "seed": 0,
                        "sklearn_version": sklearn.__version__, "n_cells": len(X),
                        "ranking": "metrics.rank_order(seed=0), fractional boundary capture"},
              "labels": info,
              "reference": {"2024_to_2025_apr_sep_capture@5%": previous["runs"]["2024_to_2025"]["capture@5%"],
                            "2025_to_2026_apr_sep_capture@5%": previous["runs"]["2025_to_2026"]["capture@5%"],
                            "original_B3_capture@5%": old["years"]["B3"]["temporal_B_env"]["capture@5%"]},
              "runs": runs,
              "limitations": ["same static feature rows are repeated across years; rows are not independent",
                              "more years change both sample size and training distribution, so this does not isolate sample-size effect",
                              "reported points and observation effort may vary by year; descriptive, not a causal shift test"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
