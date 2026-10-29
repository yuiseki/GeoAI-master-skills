"""One-shot check, on 2024, of the Akita City gain seen in R043: does B_env x (reports within 2 km in the previous
28 days + 1) capture more of next week's Akita City report cells than B_env alone? The setting is the one R043
fixed on 2025; the score is the saved B1 B_env (trained on 2023 only); 2024 weeks were never used for activation.
Plan: EXPERIMENT_PLAN.md, 2026-10-29.

From repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy --with pandas --with pyarrow \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/akita_city_activation_2024.py \
      artifacts/_bear/akita-bear-risk-grid-100m projects/_bear/akita-bear-risk-grid-100m/outputs/akita_city_activation_2024.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

from grid import Grid
import labels as lb
import metrics as mt
import same_year_spatial_oof as spatial
import seasonal_activation as sa
from seasonal_transfer_b_env import seasonal_labels

YEAR = 2024
R, ALPHA = 2000, 1  # fixed by R043 on 2025
SEASON_POSITIVES = 1132  # R036
SCORES = "eval/b1_dev_2023_to_2024_scores.npz"
SCORES_SHA256 = "743c73ac48d77169f3348971358e45b7cffd0dca58dba5ff1617929fb732404b"


def within_take(score, mask, k):
    """The share of each masked cell inside the top k of the masked cells; zero outside the mask."""
    idx = np.flatnonzero(mask)
    take = np.zeros(len(score))
    take[idx] = sa.take_fraction(mt.rank_order(np.asarray(score)[idx], seed=0), k)
    return take


def blocks_touching(blocks, mask):
    """Sorted block ids, and which of them hold at least one masked cell."""
    ids, inv = np.unique(blocks, return_inverse=True)
    return ids, np.bincount(inv, weights=mask.astype(float), minlength=len(ids)) > 0


def decision(diff):
    return {"rule": "supported if the 90% lower bound of the Akita City M - E > 0", "lower": diff[1],
            "supported": bool(diff[1] > 0)}


def diff_interval(a, b, keep, boot):
    """[M - E, lower, upper] from (hit, n) per block, resampling only the kept blocks."""
    (ha, n), (hb, _) = a, b
    ha, hb, n = ha[keep], hb[keep], n[keep]
    return [sa.pooled(ha, n) - sa.pooled(hb, n), *sa.block_interval(ha, hb, n, boot, 0)]


def main():
    import duckdb
    import pandas as pd
    import pyproj

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()
    if a.out.exists():
        raise ValueError("output already exists; refusing post-result replacement")
    path = a.art / SCORES
    if spatial.sha256(path) != SCORES_SHA256:
        raise ValueError("B1 scores differ from the preregistered file")
    meta = json.loads((a.art / "grid.json").read_text(encoding="utf-8"))
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(a.art / "grid_mask.npz") as m:
        muni = m["muni"]
    inside = muni >= 0
    shape = muni.shape
    cells = pd.read_parquet(a.art / "cells.parquet", columns=["ix", "iy"])
    iy0, ix0 = np.nonzero(inside)
    if not (np.array_equal(cells.ix.to_numpy(), ix0) and np.array_equal(cells.iy.to_numpy(), iy0)):
        raise ValueError("cells.parquet order differs from the prefecture mask")
    blocks = (ix0 // 100) * 10000 + iy0 // 100
    city = muni[inside] == meta["codes"].index(sa.AKITA_CITY_CODE)
    ids, city_blocks = blocks_touching(blocks, city)
    with np.load(a.art / "reports_by_year.npz") as s:
        known = {YEAR: s[f"c{YEAR}"]}

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", f"{YEAR}-04-01", f"{YEAR + 1}-04-01"]).fetchnumpy()
    tr = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = tr.transform(raw["longitude"], raw["latitude"])
    dates = np.asarray(raw["observed_at"], dtype="datetime64[m]")
    _, info = seasonal_labels(grid, muni, x, y, dates, known, years=(YEAR,))
    if info[YEAR]["positive_cells"] != SEASON_POSITIVES:
        raise ValueError("2024 seasonal positives differ from R036")

    with np.load(path) as s:
        env = s["B_env"].astype(np.float64)
    kern = sa.disk_kernel(R, grid.size)
    iy, ix, day = sa.season_reports(grid, muni, x, y, dates, YEAR)
    start = np.datetime64(f"{YEAR}-04-01")
    takes = {"E": sa.take_fraction(mt.rank_order(env, seed=0), sa.K), "E_city": within_take(env, city, sa.K)}
    sums = {}  # (score, subset) -> [hit per block, positives per block]
    weeks = []
    for t in sa.week_origins(YEAR):
        win, target, new = sa.week_data(iy, ix, day, t, shape, inside, start)
        m = sa.mixed(env, sa.activity(win, kern)[inside], ALPHA)
        takes["M"] = sa.take_fraction(mt.rank_order(m, seed=0), sa.K)
        takes["M_city"] = within_take(m, city, sa.K)
        subsets = {"all": target, "city": target & city, "city_new": new & city}
        row = {"origin": str(t), "positives": int(target.sum()), "city_positives": int(subsets["city"].sum()),
               "city_new_positives": int(subsets["city_new"].sum()), "window_reports": int(win[inside].sum())}
        for name, tk in takes.items():
            for sub, pos in subsets.items():
                if name.endswith("_city") and sub == "all":
                    continue
                h, n = sa.by_block([tk], [pos], blocks)
                acc = sums.setdefault((name, sub), [np.zeros(len(ids)), np.zeros(len(ids))])
                acc[0] += h
                acc[1] += n
        weeks.append(row)
        print(row, flush=True)

    capture = {f"{k[0]}|{k[1]}": sa.pooled(*v) for k, v in sums.items()}
    every = np.ones(len(ids), bool)
    primary = diff_interval(sums[("M", "city")], sums[("E", "city")], city_blocks, a.boot)
    result = {
        "plan": "EXPERIMENT_PLAN.md 2026-10-29 one-shot Akita City activation check on 2024",
        "setting": {"r": R, "alpha": ALPHA, "window_days": sa.WINDOW_DAYS, "k": sa.K, "scores": SCORES,
                    "scores_sha256": SCORES_SHA256},
        "labels": {str(YEAR): info[YEAR]}, "n_weeks": len(weeks),
        "positives": int(sum(w["positives"] for w in weeks)),
        "city_positives": int(sum(w["city_positives"] for w in weeks)),
        "city_new_positives": int(sum(w["city_new_positives"] for w in weeks)),
        "city_blocks": int(city_blocks.sum()), "capture": capture,
        "intervals_90": {
            "primary_city_M_minus_E": primary,
            "statewide_M_minus_E": diff_interval(sums[("M", "all")], sums[("E", "all")], every, a.boot),
            "city_budget_M_minus_E": diff_interval(sums[("M_city", "city")], sums[("E_city", "city")],
                                                   city_blocks, a.boot),
            "city_new_M_minus_E": diff_interval(sums[("M", "city_new")], sums[("E", "city_new")],
                                                city_blocks, a.boot)},
        "decision": decision(primary), "weeks": weeks}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "weeks"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
