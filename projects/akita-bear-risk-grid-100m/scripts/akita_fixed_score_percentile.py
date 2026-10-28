"""Akita-city positive-cell percentile shift on one saved B2 B_env score surface.

From repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/akita-bear-risk-grid-100m/scripts/akita_fixed_score_percentile.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/akita-bear-risk-grid-100m \
      projects/akita-bear-risk-grid-100m/outputs/akita_b2_fixed_score_percentile_shift.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

from grid import Grid
import labels as lb
import metrics as mt
import positive_feature_audit as feature_audit
import same_year_spatial_oof as spatial
from seasonal_transfer_b_env import seasonal_labels

YEARS = (2025, 2026)
AKITA_CITY_CODE = "05201"
TOP_PCTS = (1, 5, 10, 25)


def city_rank(scores):
    """Fixed descending score order; percentile high means high B2 score."""
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or len(scores) == 0 or not np.isfinite(scores).all():
        raise ValueError("city scores must be a finite nonempty 1-D vector")
    order = mt.rank_order(scores, seed=0)
    rank = np.empty(len(scores), dtype=np.int32)
    rank[order] = np.arange(len(scores), dtype=np.int32)
    n = len(scores)
    percentile = 1 - (rank.astype(float) + .5) / n
    decile = np.minimum((rank.astype(np.int64) * 10) // n + 1, 10).astype(np.int8)
    return rank, percentile, decile


def summarize_positive(positive, rank, percentile, decile):
    positive = np.asarray(positive)
    rank, percentile, decile = map(np.asarray, (rank, percentile, decile))
    n = len(rank)
    if positive.shape != (n,) or positive.dtype != bool or percentile.shape != (n,) \
            or decile.shape != (n,) or not np.isfinite(percentile).all():
        raise ValueError("positive cells and fixed city ranks must be aligned")
    n_positive = int(positive.sum())
    if n_positive == 0:
        raise ValueError("no positive cells in this year")
    q1, med, q3 = np.quantile(percentile[positive], [.25, .5, .75])
    top = {f"{pct}%": float(np.mean(rank[positive] < int(np.ceil(pct / 100 * n))))
           for pct in TOP_PCTS}
    rows = [{"decile": f"D{i}", "n_positive": int(np.count_nonzero(positive & (decile == i))),
             "share_of_positives": float(np.mean(decile[positive] == i))}
            for i in range(1, 11)]
    if sum(row["n_positive"] for row in rows) != n_positive \
            or not np.isclose(sum(row["share_of_positives"] for row in rows), 1):
        raise ValueError("score deciles do not partition positive city cells")
    return {"n_positive": n_positive,
            "percentile": {"q25": float(q1), "median": float(med), "q75": float(q3)},
            "top_share": top, "deciles": rows}


def compare_years(y25, y26, rank, percentile, decile):
    first = summarize_positive(y25, rank, percentile, decile)
    second = summarize_positive(y26, rank, percentile, decile)
    stats = feature_audit.summarize_feature(percentile[np.asarray(y26)], percentile[np.asarray(y25)])
    rows = []
    for before, after in zip(first["deciles"], second["deciles"]):
        change = after["share_of_positives"] - before["share_of_positives"]
        rows.append({"decile": before["decile"], "share_2025": before["share_of_positives"],
                     "share_2026": after["share_of_positives"], "change_2026_minus_2025": change})
    rows.sort(key=lambda row: (-row["change_2026_minus_2025"], row["decile"]))
    return {"years": {"2025": first, "2026": second},
            "cliffs_delta_2026_minus_2025": stats["cliffs_delta"],
            "ks_statistic": stats["ks_statistic"],
            "decile_share_changes": rows,
            "largest_decile_share_increases": rows[:3]}


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
    prior_path = project / "outputs/b2_fixed_score_municipal_decomposition.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    if prior["setup"]["source"] != lb.SIGHTING:
        raise ValueError("fixed sighting source differs")
    fixed_files = ("grid_mask.npz", "reports_by_year.npz", "cells.parquet",
                   "worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz")
    hashes = {name: spatial.sha256(args.art / name) for name in fixed_files}
    if hashes != prior["setup"]["fixed_input_sha256"]:
        raise ValueError("fixed input artifacts changed")
    grid_path = args.art / "grid.json"
    meta = json.loads(grid_path.read_text(encoding="utf-8"))
    if spatial.sha256(grid_path) != prior["setup"]["grid_json_sha256"] \
            or meta["crs"] != "EPSG:6678" or meta["size"] != 100:
        raise ValueError("fixed 100m grid changed")
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(args.art / "grid_mask.npz") as masked:
        muni = masked["muni"]
    inside = muni >= 0
    if muni.shape != (grid.ny, grid.nx) or int(inside.sum()) != prior["setup"]["n_prefecture_cells"]:
        raise ValueError("prefecture mask differs from earlier audit")
    city_index = meta["codes"].index(AKITA_CITY_CODE)
    city = muni[inside] == city_index
    with np.load(args.art / "reports_by_year.npz") as saved:
        known = {year: saved[f"c{year}"] for year in YEARS}
    score_path = args.art / "eval/b2_confirm_2023-2024_to_2025_scores.npz"
    if spatial.sha256(score_path) != prior["setup"]["b2_score_npz_sha256"]:
        raise ValueError("saved B2 score file changed")
    with np.load(score_path) as saved_scores:
        scores = saved_scores["B_env"]
    if scores.shape != (int(inside.sum()),):
        raise ValueError("saved score vector is not aligned with prefecture cells")
    rank, percentile, decile = city_rank(scores[city])
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2025-04-01", "2026-10-01"]).fetchnumpy()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = transformer.transform(raw["longitude"], raw["latitude"])
    counts, info = seasonal_labels(grid, muni, x, y, raw["observed_at"], known, years=YEARS)
    labels = {}
    for year in YEARS:
        if info[year] != prior["labels"][str(year)]:
            raise ValueError(f"{year} fixed seasonal label metadata differs")
        positives = counts[year][inside] > 0
        labels[year] = positives[city]
        if int(labels[year].sum()) != prior["akita_city"][str(year)]["n_positive"] \
                or int(positives.sum()) != prior["years"][str(year)]["n_positive"]:
            raise ValueError(f"{year} Akita or prefecture positive cell count differs")
    compared = compare_years(labels[2025], labels[2026], rank, percentile, decile)
    result = {"mode": "descriptive Akita-city rank-shift audit on one saved B2 B_env score; no fitting",
              "definition": {"city": "Akita city, fixed grid_mask.npz municipality code 05201",
                             "score_percentile": "1-(zero_based_city_rank+0.5)/n_city_cells; high means high saved B2 score",
                             "rank": "metrics.rank_order(score,seed=0) on Akita city cells once for both years",
                             "city_top_percent": "rank < ceil(k*n_city_cells), k=1,5,10,25; not the prefecture-wide top set",
                             "deciles": "D1 highest 10% ... D10 lowest 10%; floor(10*rank/n)+1",
                             "positive": "one or more fixed-source bear reports in Apr–Sep 100m cell",
                             "cliffs_delta": "later (2026) minus earlier (2025) percentile orientation; negative means lower scores",
                             "ks": "two-sample KS statistic; no p-value decision"},
              "setup": {"source": lb.SIGHTING, "grid_json_sha256": spatial.sha256(grid_path),
                        "fixed_input_sha256": hashes, "b2_score_npz_sha256": spatial.sha256(score_path),
                        "prior_decomposition_json_sha256": spatial.sha256(prior_path),
                        "n_city_cells": int(city.sum()),
                        "city_top_selected_cells": {f"{pct}%": int(np.ceil(pct / 100 * len(rank))) for pct in TOP_PCTS}},
              "labels": info, **compared,
              "limitations": ["within-city top 5% is not the prefecture-wide top 5% used for prior recall",
                              "fixed score-percentile shifts are descriptive, not causal explanations",
                              "reported coordinates and reporting effort may vary between years"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("city cells:", int(city.sum()), flush=True)
    print("summary:", compared, flush=True)


if __name__ == "__main__":
    main()
