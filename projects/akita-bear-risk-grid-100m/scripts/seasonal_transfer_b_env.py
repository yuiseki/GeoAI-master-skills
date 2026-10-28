"""Fixed two-run Apr–Sep B_env transfer diagnostic (2024→2025, 2025→2026).

Run from repository root with the same uvx dependencies as partial_2025_spatial_oof.py:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/akita-bear-risk-grid-100m/scripts/seasonal_transfer_b_env.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/akita-bear-risk-grid-100m \
      projects/akita-bear-risk-grid-100m/outputs/apr_sep_year_transfer_b_env.json
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

YEARS = (2024, 2025, 2026)
TRANSFERS = ((2024, 2025), (2025, 2026))


def seasonal_labels(grid, muni, x, y, observed_at, known_full, years=YEARS):
    """Build identical Apr–Sep labels after exact fixed full-year reconciliation."""
    dates = np.asarray(observed_at, dtype="datetime64[m]")
    x, y = np.asarray(x), np.asarray(y)
    if dates.ndim != 1 or x.shape != dates.shape or y.shape != dates.shape or np.isnat(dates).any():
        raise ValueError("unaligned or missing source coordinates/dates")
    fiscal_years = lb.bear_year(dates)
    full, full_off = lb.counts_by_year(grid, muni, x, y, fiscal_years, years)
    inside = muni >= 0
    counts, info = {}, {}
    for yr in years:
        if yr not in known_full or known_full[yr].shape != muni.shape \
                or not np.array_equal(full[yr], known_full[yr]):
            raise ValueError(f"source reports do not reproduce saved c{yr}")
        start = np.datetime64(f"{yr}-04-01T00:00", "m")
        end = np.datetime64(f"{yr}-10-01T00:00", "m")
        sel = (dates >= start) & (dates < end)
        part, off = lb.counts_by_year(grid, muni, x[sel], y[sel], fiscal_years[sel], [yr])
        counts[yr] = part[yr]
        if np.any(counts[yr] > full[yr]) or int(counts[yr][inside].sum()) + off[yr] != int(sel.sum()):
            raise ValueError(f"seasonal counts do not reconcile for {yr}")
        info[yr] = {"window_start_inclusive": str(start), "window_end_exclusive": str(end),
                    "full_inside_reports": int(full[yr][inside].sum()),
                    "full_outside_reports": full_off[yr],
                    "inside_window_reports": int(counts[yr][inside].sum()),
                    "outside_window_reports": off[yr],
                    "positive_cells": int((counts[yr][inside] > 0).sum())}
    return counts, info


def fit_transfer(X, train_y, model_factory=None):
    from sklearn.ensemble import HistGradientBoostingClassifier

    X = np.asarray(X)
    train_y = np.asarray(train_y)
    if X.ndim != 2 or X.shape[1] != 28 or train_y.shape != (len(X),) \
            or train_y.dtype != bool or np.unique(train_y).size != 2:
        raise ValueError("invalid fixed B_env design or train labels")
    model = (model_factory() if model_factory is not None else
             HistGradientBoostingClassifier(**me.HGB, random_state=0))
    model.fit(X, train_y)
    scores = np.asarray(model.predict_proba(X)[:, 1], dtype=np.float64)
    if scores.shape != (len(X),) or not np.isfinite(scores).all():
        raise ValueError("invalid transfer scores")
    return scores


def main():
    import duckdb
    import pyproj
    import sklearn

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    if args.out.exists():
        raise ValueError("one-run output already exists; refusing additional exploration")
    project = Path(__file__).resolve().parents[1]
    old_path = project / "outputs/b2_b3_same_year_spatial_oof.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    setup = old["setup"]
    if setup["hgb"] != me.HGB or setup["random_state"] != 0 \
            or setup["sklearn_version"] != sklearn.__version__:
        raise ValueError("fixed HGB/seed/scikit-learn version mismatch")
    relevant = ("grid_mask.npz", "reports_by_year.npz", "cells.parquet",
                "worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz")
    hashes = {name: spatial.sha256(args.art / name) for name in relevant}
    if any(hashes[name] != setup["input_sha256"][name] for name in relevant):
        raise ValueError("fixed data hashes differ from earlier B_env run")
    grid_path = args.art / "grid.json"
    meta = json.loads(grid_path.read_text(encoding="utf-8"))
    if meta["crs"] != "EPSG:6678" or meta["size"] != 100:
        raise ValueError("grid specification changed")
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(args.art / "grid_mask.npz") as mask:
        muni = mask["muni"]
    inside = muni >= 0
    if int(inside.sum()) != old["years"]["B2"]["n_cells"]:
        raise ValueError("prefecture cell count differs")
    with np.load(args.art / "reports_by_year.npz") as reports:
        known = {yr: reports[f"c{yr}"] for yr in YEARS}

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2024-04-01", "2026-10-01"]).fetchnumpy()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = transformer.transform(raw["longitude"], raw["latitude"])
    counts, label_info = seasonal_labels(grid, muni, x, y, raw["observed_at"], known)
    prior = json.loads((project / "outputs/b2_2025_apr_sep_spatial_oof.json").read_text(encoding="utf-8"))
    if label_info[2025]["positive_cells"] != prior["label"]["n_window_positive_cells"] \
            or label_info[2025]["inside_window_reports"] != prior["label"]["n_window_inside_reports"] \
            or label_info[2025]["outside_window_reports"] != prior["label"]["n_window_outside_prefecture_cells"] \
            or label_info[2026]["positive_cells"] != old["years"]["B3"]["n_positive"]:
        raise ValueError("seasonal labels differ from previously validated years")
    print("labels reconciled:", label_info, flush=True)
    with np.load(args.art / "worldcover.npz") as wc, np.load(args.art / "dem.npz") as dem, \
            np.load(args.art / "worldpop.npz") as pop, np.load(args.art / "osm.npz") as osm:
        static = ft.static_features(wc, dem, pop, osm)
    names = list(static)
    if names != setup["feature_names"] or len(names) != 28:
        raise ValueError("static B_env features changed")
    X = np.column_stack([static[name][inside] for name in names]).astype(np.float32)
    del static
    labels = {yr: counts[yr][inside] > 0 for yr in YEARS}
    runs = {}
    for train_year, test_year in TRANSFERS:
        scores = fit_transfer(X, labels[train_year])
        metrics = spatial.score_metrics(scores, labels[test_year])
        key = f"{train_year}_to_{test_year}"
        runs[key] = {"train_year": train_year, "test_year": test_year,
                     "train_positive_cells": int(labels[train_year].sum()),
                     "test_positive_cells": int(labels[test_year].sum()), **metrics}
        print(key, runs[key], flush=True)
    delta = runs["2025_to_2026"]["capture@5%"] - runs["2024_to_2025"]["capture@5%"]
    output = {"mode": "exploratory year transfer; two fixed Apr-Sep runs only",
              "setup": {"source": lb.SIGHTING, "grid_json_sha256": spatial.sha256(grid_path),
                        "fixed_input_sha256": hashes, "previous_oof_json_sha256": spatial.sha256(old_path),
                        "previous_2025_partial_json_sha256": spatial.sha256(project / "outputs/b2_2025_apr_sep_spatial_oof.json"),
                        "feature_names": names, "hgb": me.HGB, "seed": 0,
                        "sklearn_version": sklearn.__version__, "n_cells": len(X),
                        "ranking": "metrics.rank_order(seed=0), fractional boundary capture"},
              "labels": label_info, "runs": runs,
              "capture@5%_2025_to_2026_minus_2024_to_2025": delta,
              "limitations": ["reported location is not exact bear location; observation effort may vary",
                              "static features have their original vintage; this is not a causal shift test",
                              "same prefecture cells across years, not spatial holdout; no model selection"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
