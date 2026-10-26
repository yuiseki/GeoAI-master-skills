"""Score risk maps on a grid of cells by an area budget: of the cells where the event happened in the test period,
how many fall in the top k of all cells by the map's score (capture@k).

    rank_order(score, second)   the order of the cells: by the score, then a second key, then at random with a seed,
                                so ties are broken the same way for every resample
    capture(order, pos, k, w)   the share of the positives (or of the counts) in the top k of the total weight; the cell
                                that straddles the cut counts by its fraction
    bootstrap_diff(...)         90% interval of capture(a) - capture(b), resampling whole blocks with replacement and
                                taking the top k again inside every resample
    coarsen(...)                cells gathered into coarser cells: positive when any cell is; a probability becomes
                                1 - prod(1 - p), any other score the mean over the cells

Usage:
    uvx --with numpy --with pandas --with pyarrow python score_risk_map.py TABLE.parquet --label COL --scores A B \\
        [--second A=COL] [--block COL] [--ks 0.01 0.05 0.10] [--compare A:B] [--boot 1000] [--seed 0] \\
        [--grid ix iy --factors 5 10 --prob A] [--out OUT.json]

TABLE has one row per cell: the label of the test period (a count or 0/1; positive means > 0), one column per map's
score, and, for the interval, a block id (cells grouped into blocks well larger than the reach of the dependence).
"""

import argparse
import json

import numpy as np


def rank_order(score, second=None, seed=0):
    rng = np.random.default_rng(seed)
    keys = [rng.random(len(score))]
    if second is not None:
        keys.append(-np.nan_to_num(np.asarray(second, dtype=float), nan=-np.inf))
    keys.append(-np.nan_to_num(np.asarray(score, dtype=float), nan=-np.inf))
    return np.lexsort(keys)


def capture(order, pos, k, weights=None):
    w = np.ones(len(order)) if weights is None else np.asarray(weights, dtype=float)
    pos = np.asarray(pos, dtype=float)
    total = float((w * pos).sum())
    if total == 0:
        return float("nan")
    wo, po = w[order], pos[order]
    cut = k * wo.sum()
    prev = np.cumsum(wo) - wo
    take = np.clip((cut - prev) / np.where(wo > 0, wo, 1), 0, 1) * (wo > 0)
    return float((take * wo * po).sum() / total)


def bootstrap_diff(order_a, order_b, pos, blocks, k, B=1000, seed=0):
    ids, inv = np.unique(blocks, return_inverse=True)
    rng = np.random.default_rng(seed)
    diffs = np.empty(B)
    for b in range(B):
        w = np.bincount(rng.integers(0, len(ids), len(ids)), minlength=len(ids)).astype(float)[inv]
        diffs[b] = capture(order_a, pos, k, w) - capture(order_b, pos, k, w)
    return float(np.quantile(diffs, 0.05)), float(np.quantile(diffs, 0.95))


def coarsen(ix, iy, pos, score, factor, prob):
    key = (np.asarray(ix) // factor) * 10_000_000 + np.asarray(iy) // factor
    _, inv = np.unique(key, return_inverse=True)
    n = np.bincount(inv)
    lab = np.bincount(inv, weights=(np.asarray(pos) > 0).astype(float)) > 0
    if prob:
        s = 1 - np.exp(np.bincount(inv, weights=np.log1p(-np.clip(score, 0, 1 - 1e-12))))
    else:
        s = np.bincount(inv, weights=score) / n
    return lab, s


def main():
    import pandas as pd

    ap = argparse.ArgumentParser()
    ap.add_argument("table")
    ap.add_argument("--label", required=True)
    ap.add_argument("--scores", nargs="+", required=True)
    ap.add_argument("--second", nargs="*", default=[], help="SCORE=COLUMN: the second key for ties of that score")
    ap.add_argument("--block", default=None)
    ap.add_argument("--ks", type=float, nargs="+", default=[0.01, 0.05, 0.10])
    ap.add_argument("--k", type=float, default=0.05, help="the budget of the comparisons and the coarser cells")
    ap.add_argument("--compare", nargs="*", default=[], help="A:B pairs: capture@k of A minus B, with a block interval")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--grid", nargs=2, default=None, metavar=("IX", "IY"), help="integer cell columns, for --factors")
    ap.add_argument("--factors", type=int, nargs="*", default=[])
    ap.add_argument("--prob", nargs="*", default=[], help="scores that are probabilities (gathered as 1 - prod(1 - p))")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    df = pd.read_parquet(a.table)
    n_in = len(df)
    need = [a.label] + a.scores + ([a.block] if a.block else []) + (list(a.grid) if a.grid else [])
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"columns not in the table: {missing}")
    if df[a.label].isna().any():
        raise SystemExit(f"{int(df[a.label].isna().sum())} rows have no label: a missing label is not a 0")
    counts = df[a.label].to_numpy(dtype=float)
    pos = counts > 0
    second = dict(s.split("=", 1) for s in a.second)
    orders = {m: rank_order(df[m].to_numpy(float), df[second[m]].to_numpy(float) if m in second else None, a.seed) for m in a.scores}
    res = {"rows": n_in, "positive_cells": int(pos.sum()), "positive_share": float(pos.mean()), "maps": {}, "compare": {}}
    for m, o in orders.items():
        r = {f"capture@{k:g}": capture(o, pos, k) for k in a.ks}
        r[f"capture@{a.k:g}_counts"] = capture(o, counts, a.k)
        res["maps"][m] = r
    res["oracle"] = {f"capture@{k:g}": capture(rank_order(counts), pos, k) for k in a.ks}
    for pair in a.compare:
        x, y = pair.split(":")
        d = capture(orders[x], pos, a.k) - capture(orders[y], pos, a.k)
        item = {"diff": d}
        if a.block:
            lo, hi = bootstrap_diff(orders[x], orders[y], pos, df[a.block].to_numpy(), a.k, a.boot, a.seed)
            item.update({"lo90": lo, "hi90": hi, "blocks": int(df[a.block].nunique()), "boot": a.boot})
        res["compare"][f"{x} - {y}"] = item
    if a.grid and a.factors:
        res["coarser"] = {}
        for f in a.factors:
            row = {}
            for m in a.scores:
                lab, s = coarsen(df[a.grid[0]], df[a.grid[1]], counts, df[m].to_numpy(float), f, m in a.prob)
                row[m] = capture(rank_order(s), lab, a.k)
            row["oracle"] = capture(rank_order(lab.astype(float)), lab, a.k)
            row["coarse_cells"] = int(len(lab))
            row["positive_share"] = float(lab.mean())
            res["coarser"][str(f)] = row
    text = json.dumps(res, indent=1)
    print(text)
    if a.out:
        open(a.out, "w").write(text)


if __name__ == "__main__":
    main()
