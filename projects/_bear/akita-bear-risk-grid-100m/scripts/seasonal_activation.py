"""Within-season activation: does the number of reports near a cell in the previous 28 days, multiplied onto the
static B_env score, find next week's report cells better than B_env alone? No refitting: the saved B2 scores
(trained on 2023+2024) are used for 2025 (development: choose the radius r and the smoothing alpha) and the saved
B3 scores (trained on 2023-2025) for 2026 (one confirmation). Plan: EXPERIMENT_PLAN.md, 2026-10-28.

From repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy --with pandas --with pyarrow \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/seasonal_activation.py \
      artifacts/_bear/akita-bear-risk-grid-100m projects/_bear/akita-bear-risk-grid-100m/outputs/seasonal_activation.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

from grid import Grid
import labels as lb
import metrics as mt
import same_year_spatial_oof as spatial
from seasonal_transfer_b_env import seasonal_labels

K = 0.05
RADII = (500, 1000, 2000)
ALPHAS = (0.1, 0.3, 1, 3)
WINDOW_DAYS = 28
DAY = np.timedelta64(1, "D")
AKITA_CITY_CODE = "05201"
SEASON_POSITIVES = {2025: 3657, 2026: 3036}  # R036
SCORES = {2025: "eval/b2_confirm_2023-2024_to_2025_scores.npz", 2026: "eval/b3_confirm_2023-2025_to_2026_scores.npz"}


def disk_kernel(r, size):
    """1 where the cell centre lies within r of the middle cell's centre."""
    m = int(r // size)
    i, j = np.mgrid[-m:m + 1, -m:m + 1]
    return ((i * i + j * j) * size * size <= r * r + 1e-9).astype(float)


def activity(counts, kernel):
    """Reports whose cell centre is within the kernel of each cell, as integers."""
    from scipy.signal import fftconvolve

    return np.rint(fftconvolve(np.asarray(counts, dtype=float), kernel, mode="same")).astype(np.int32)


def week_origins(year):
    """Mondays from the first on or after 1 May to the last whose week ends by 1 October."""
    may = np.datetime64(f"{year}-05-01")
    weekday = (may.astype(int) + 3) % 7  # 1970-01-01 was a Thursday; Monday is 0
    first = may + int((7 - weekday) % 7) * DAY
    end = np.datetime64(f"{year}-10-01")
    return np.arange(first, end - 6 * DAY, 7 * DAY)


def take_fraction(order, k):
    """The share of each cell inside the top k of all cells, the straddling cell by its fraction (metrics.capture)."""
    n = len(order)
    take = np.empty(n)
    take[order] = np.clip(k * n - np.arange(n), 0, 1)
    return take


def mixed(env, act, alpha):
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    return np.asarray(env, dtype=float) * (np.asarray(act, dtype=float) + alpha)


def by_block(takes, positives, blocks):
    """(captured, positives) per block, summed over the weeks."""
    ids, inv = np.unique(blocks, return_inverse=True)
    hit = np.zeros(len(ids))
    n = np.zeros(len(ids))
    for take, pos in zip(takes, positives):
        hit += np.bincount(inv, weights=take * pos, minlength=len(ids))
        n += np.bincount(inv, weights=pos.astype(float), minlength=len(ids))
    return hit, n


def pooled(hit, n):
    return float(hit.sum() / n.sum())


def block_interval(hit_a, hit_b, n, B=2000, seed=0):
    """90% interval of pooled(a) - pooled(b), resampling blocks with the selections fixed."""
    rng = np.random.default_rng(seed)
    nb = len(n)
    d = np.empty(B)
    for b in range(B):
        m = np.bincount(rng.integers(0, nb, nb), minlength=nb)
        d[b] = ((hit_a - hit_b) * m).sum() / max((n * m).sum(), 1e-12)
    return float(np.quantile(d, .05)), float(np.quantile(d, .95))


def choose(rows):
    return min(rows, key=lambda r: (-r["capture"], r["r"], -r["alpha"]))


def season_reports(grid, muni, x, y, dates, year):
    """Cell index (into the prefecture cells) and date of each in-season report inside the prefecture."""
    start, end = np.datetime64(f"{year}-04-01T00:00", "m"), np.datetime64(f"{year}-10-01T00:00", "m")
    ix, iy, ok = grid.index(x, y)
    keep = ok & (dates >= start) & (dates < end)
    keep[keep] = muni[iy[keep], ix[keep]] >= 0
    return iy[keep], ix[keep], dates[keep].astype("datetime64[D]")


def grid_counts(iy, ix, sel, shape):
    return np.bincount(iy[sel] * shape[1] + ix[sel], minlength=shape[0] * shape[1]).reshape(shape)


def week_data(iy, ix, day, t, shape, inside, start):
    """Window counts on the grid, target positives, and positives in cells with no report since 1 April."""
    win = grid_counts(iy, ix, (day >= t - WINDOW_DAYS * DAY) & (day < t), shape)
    target = grid_counts(iy, ix, (day >= t) & (day < t + 7 * DAY), shape)[inside] > 0
    before = grid_counts(iy, ix, (day >= start) & (day < t), shape)[inside] > 0
    return win, target, target & ~before


def run_week(env, env_take, win, inside, configs, kernels):
    """Takes of E, A_r and M_(r, alpha) for one week."""
    out = {"E": env_take}
    for r, kern in kernels.items():
        act = activity(win, kern)[inside]
        for c in configs:
            if c == ("A", r):
                out[c] = take_fraction(mt.rank_order(act, second=env, seed=0), K)
            elif c[0] == r:
                out[c] = take_fraction(mt.rank_order(mixed(env, act, c[1]), seed=0), K)
    return out


class Tally:
    """Per-block captured and positive counts, summed over weeks, for all positives, new cells and Akita city."""

    def __init__(self, blocks, city):
        self.ids, self.inv = np.unique(blocks, return_inverse=True)
        self.city = city
        self.sums = {s: [np.zeros(len(self.ids)), np.zeros(len(self.ids))] for s in ("all", "new", "city")}

    def add(self, take, target, new):
        for s, pos in (("all", target), ("new", new), ("city", target & self.city)):
            h, n = by_block([take], [pos], self.inv)
            self.sums[s][0] += h
            self.sums[s][1] += n


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
    city = muni[inside] == meta["codes"].index(AKITA_CITY_CODE)
    with np.load(a.art / "reports_by_year.npz") as s:
        known = {y: s[f"c{y}"] for y in (2025, 2026)}

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2025-04-01", "2026-10-01"]).fetchnumpy()
    tr = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = tr.transform(raw["longitude"], raw["latitude"])
    dates = np.asarray(raw["observed_at"], dtype="datetime64[m]")
    _, info = seasonal_labels(grid, muni, x, y, dates, known, years=(2025, 2026))
    for yr, n in SEASON_POSITIVES.items():
        if info[yr]["positive_cells"] != n:
            raise ValueError(f"{yr} seasonal positives differ from R036")

    kernels = {r: disk_kernel(r, grid.size) for r in RADII}
    result = {"plan": "EXPERIMENT_PLAN.md 2026-10-28 within-season activation", "k": K, "window_days": WINDOW_DAYS,
              "labels": {str(k): v for k, v in info.items()}, "score_sha256": {}, "years": {}}
    chosen = None
    for year in (2025, 2026):
        path = a.art / SCORES[year]
        result["score_sha256"][str(year)] = spatial.sha256(path)
        with np.load(path) as s:
            env = s["B_env"].astype(np.float64)
        iy, ix, day = season_reports(grid, muni, x, y, dates, year)
        start = np.datetime64(f"{year}-04-01")
        env_take = take_fraction(mt.rank_order(env, seed=0), K)
        if year == 2025:
            configs = [(r, al) for r in RADII for al in ALPHAS] + [("A", r) for r in RADII]
        else:
            configs = [(chosen["r"], chosen["alpha"]), ("A", chosen["r"])]
        tallies = {c: Tally(blocks, city) for c in configs + ["E"]}
        radii = {c[1] if c[0] == "A" else c[0] for c in configs}
        weeks = []
        for t in week_origins(year):
            win, target, new = week_data(iy, ix, day, t, shape, inside, start)
            res = run_week(env, env_take, win, inside, configs, {r: kernels[r] for r in radii})
            row = {"origin": str(t), "positives": int(target.sum()), "new_positives": int(new.sum()),
                   "window_reports": int(win[inside].sum())}
            for c, tk in res.items():
                tallies[c].add(tk, target, new)
                row[str(c)] = float((tk * target).sum() / target.sum()) if target.any() else None
            weeks.append(row)
            print(year, row["origin"], row["positives"], round(row["E"] or 0, 3),
                  max((round(v, 3) for k, v in row.items() if k.startswith("(") and v is not None), default=None),
                  flush=True)
        summary = {str(c): {"capture": pooled(*tl.sums["all"]), "new_capture": pooled(*tl.sums["new"]),
                            "akita_city_capture": pooled(*tl.sums["city"])} for c, tl in tallies.items()}
        ydata = {"weeks": weeks, "n_weeks": len(weeks), "positives": int(sum(w["positives"] for w in weeks)),
                 "new_positives": int(sum(w["new_positives"] for w in weeks)), "summary": summary}
        if year == 2025:
            grid_rows = [{"r": r, "alpha": al, "capture": summary[str((r, al))]["capture"]}
                         for r in RADII for al in ALPHAS]
            chosen = choose(grid_rows)
            ydata["development_grid"] = grid_rows
            ydata["chosen"] = chosen
        mc, ac = (chosen["r"], chosen["alpha"]), ("A", chosen["r"])
        he, n = tallies["E"].sums["all"]
        hen, nn = tallies["E"].sums["new"]
        hm, hmn, ha = tallies[mc].sums["all"][0], tallies[mc].sums["new"][0], tallies[ac].sums["all"][0]
        ydata["intervals_90"] = {
            "M_minus_E": [pooled(hm, n) - pooled(he, n), *block_interval(hm, he, n, a.boot, 0)],
            "A_minus_E": [pooled(ha, n) - pooled(he, n), *block_interval(ha, he, n, a.boot, 0)],
            "M_minus_E_new_cells": [pooled(hmn, nn) - pooled(hen, nn), *block_interval(hmn, hen, nn, a.boot, 0)]}

        # season version: activity from April-May, targets June to September
        t = np.datetime64(f"{year}-06-01")
        win = grid_counts(iy, ix, day < t, shape)
        target = grid_counts(iy, ix, day >= t, shape)[inside] > 0
        new = target & ~(win[inside] > 0)
        act = activity(win, kernels[chosen["r"]])[inside]
        tm = take_fraction(mt.rank_order(mixed(env, act, chosen["alpha"]), seed=0), K)
        (sm, sn), (se, _) = by_block([tm], [target], blocks), by_block([env_take], [target], blocks)
        (smn, snn), (sen, _) = by_block([tm], [new], blocks), by_block([env_take], [new], blocks)
        ydata["season_version"] = {
            "window_reports": int(win[inside].sum()), "positives": int(target.sum()), "new_positives": int(new.sum()),
            "E": pooled(se, sn), "M": pooled(sm, sn), "E_new": pooled(sen, snn), "M_new": pooled(smn, snn),
            "M_minus_E": [pooled(sm, sn) - pooled(se, sn), *block_interval(sm, se, sn, a.boot, 0)]}
        result["years"][str(year)] = ydata
        print(year, json.dumps({k: v for k, v in ydata.items() if k != "weeks"}, ensure_ascii=False), flush=True)

    lo = result["years"]["2026"]["intervals_90"]["M_minus_E"][1]
    result["decision"] = {"rule": "supported if the 2026 lower 90% bound of M - E > 0", "lower": lo,
                          "supported": bool(lo > 0)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
