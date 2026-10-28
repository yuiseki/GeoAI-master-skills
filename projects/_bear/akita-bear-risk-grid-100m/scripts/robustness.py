"""Robustness of the comparison (plan block B4): the same scores and labels gathered into coarser cells, and
M_full refitted with other random seeds.

Coarser cells (500 m = 5 x 5, 1 km = 10 x 10 of the 100 m cells, on the same grid edges): a coarse cell is
positive when any of its cells is; a model probability becomes 1 - prod(1 - p) over its cells; a baseline
density (B_hist, B_pop), which is not a probability, becomes the mean over its cells. The plan named only the
first rule; the second is set here, before the coarse numbers are seen. Coarse cells keep the prefecture's
cells only, so a cell on the border has fewer than 25 or 100.

Usage:
    ... python robustness.py ART_DIR SCORES.npz TEST_YEAR OUT.json [--seeds 1 2 --train 2023 2024]
"""

import argparse
import json

import numpy as np

import metrics as mt


def coarsen(ix, iy, pos, score, factor, how):
    key = (ix // factor) * 100000 + iy // factor
    keys, inv = np.unique(key, return_inverse=True)
    n = np.bincount(inv)
    lab = np.bincount(inv, weights=pos.astype(float)) > 0
    if how == "prob":
        s = 1 - np.exp(np.bincount(inv, weights=np.log1p(-np.clip(score, 0, 1 - 1e-12))))
    else:
        s = np.bincount(inv, weights=score) / n
    return lab, s, n


def main():
    import pandas as pd

    import model_eval as me

    ap = argparse.ArgumentParser()
    ap.add_argument("art")
    ap.add_argument("scores")
    ap.add_argument("test", type=int)
    ap.add_argument("out")
    ap.add_argument("--seeds", type=int, nargs="*", default=[])
    ap.add_argument("--train", type=int, nargs="*", default=[])
    a = ap.parse_args()
    cells = pd.read_parquet(f"{a.art}/cells.parquet", columns=["ix", "iy"])
    ix, iy = cells.ix.to_numpy(), cells.iy.to_numpy()
    static, counts, muni = me.load(a.art)
    _, _, y, _ = me.design(static, counts, muni, a.test, history=False)
    sc = np.load(a.scores)
    res = {"test": a.test, "units": {}}
    for factor, name in ((1, "100m"), (5, "500m"), (10, "1km")):
        row = {}
        for m, how in (("M_full", "prob"), ("B_env", "prob"), ("B_hist", "mean"), ("B_pop", "mean")):
            lab, s, n = coarsen(ix, iy, y, sc[m].astype(float), factor, how)
            row[m] = mt.capture(mt.rank_order(s), lab, 0.05)
        row["oracle"] = mt.capture(mt.rank_order(lab.astype(float)), lab, 0.05)  # the most that 5% can hold
        row["coarse_cells"] = int(len(lab))
        row["positive_share"] = float(lab.mean())
        row["M_full - B_hist"] = row["M_full"] - row["B_hist"]
        row["M_full - B_pop"] = row["M_full"] - row["B_pop"]
        res["units"][name] = row
        print(name, {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()})
    if a.seeds:
        caps = {}
        for s in a.seeds:
            out = me.run_models(static, counts, muni, a.train, a.test, ["M_full"], seed=s)
            caps[s] = mt.capture(mt.rank_order(out["M_full"]), y, 0.05)
            print("seed", s, round(caps[s], 4))
        res["seeds_capture@5%"] = caps
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
