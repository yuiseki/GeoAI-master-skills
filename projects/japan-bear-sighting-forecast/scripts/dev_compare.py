"""Development-period comparison of a candidate with the baselines, from evaluate.py predictions (exploratory).

Per horizon: mean MAE of each model; the paired per-origin MAE difference (candidate minus naive and minus
mean_short) with a 90% interval from resampling 13-week blocks of origins (2,000 draws, seed 0); and
MAE / bias / capture by season of the target week. Writes CSVs next to OUT_PREFIX.

Usage:
    uvx --with numpy --with pandas --with pyarrow python dev_compare.py PREDICTIONS.parquet OUT_PREFIX [--candidate hgb_nb]
"""

import argparse

import numpy as np
import pandas as pd

from evaluate import block_bootstrap_interval, capture


def origin_blocks(origin_weeks, size=13):
    order = sorted(set(origin_weeks))
    return {w: i // size for i, w in enumerate(order)}


def season(week):
    m = int(week[5:7])
    return "1 Jan-Mar" if m <= 3 else "2 Apr-May" if m <= 5 else "3 Jun-Aug" if m <= 8 else "4 Sep-Dec"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions")
    ap.add_argument("out_prefix")
    ap.add_argument("--candidate", default="hgb_nb")
    a = ap.parse_args()
    df = pd.read_parquet(a.predictions)
    df["err"] = (df.pred - df.actual).abs()
    po = df.groupby(["model", "h", "origin_week"], as_index=False).err.mean()
    blocks = origin_blocks(po.origin_week.tolist())
    rows = []
    for h in sorted(po.h.unique()):
        c = po[(po.model == a.candidate) & (po.h == h)].set_index("origin_week").err
        for base in ("naive", "mean_short", "seasonal_3y"):
            b = po[(po.model == base) & (po.h == h)].set_index("origin_week").err
            d = (c - b).dropna()
            lo, hi = block_bootstrap_interval(d.to_numpy(), np.array([blocks[w] for w in d.index]), B=2000, seed=0)
            rows.append({"h": h, "candidate": a.candidate, "versus": base, "mae_candidate": c.mean(), "mae_versus": b.mean(),
                         "diff": d.mean(), "lo90": lo, "hi90": hi, "n_origins": len(d)})
    t1 = pd.DataFrame(rows)
    t1.to_csv(a.out_prefix + "_paired.csv", index=False)
    print(t1.round(3).to_string(index=False))

    df["season"] = df.target_week.map(season)
    rows = []
    for (m, h, s), g in df.groupby(["model", "h", "season"]):
        caps = []
        for _, gg in g.groupby("origin_week"):
            caps.append(capture(gg.pred.to_numpy(), gg.actual.to_numpy(), -np.arange(len(gg), dtype=float), k=5))
        rows.append({"model": m, "h": h, "season": s, "n": len(g), "mae": g.err.mean(), "bias": (g.pred - g.actual).mean(),
                     "capture5": np.nanmean(caps) if not np.all(np.isnan(caps)) else np.nan})
    t2 = pd.DataFrame(rows)
    t2.to_csv(a.out_prefix + "_by_season.csv", index=False)
    print(t2[t2.h.isin([1, 4]) & t2.model.isin(["naive", "mean_short", a.candidate])].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
