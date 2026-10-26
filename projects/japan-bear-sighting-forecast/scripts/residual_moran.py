"""Moran's I of the forecast residuals (actual - forecast) per target week, from evaluate.py predictions.

For each target week and horizon the residuals over the municipalities get a Moran's I with the row-normalised
neighbour weights. Reported per model and horizon: the mean of I over the weeks where the residuals are not
all equal, and the share of those weeks with I above 0. No p-values: the weeks and the municipalities are
dependent, so a per-week test would overstate.

Usage:
    uvx --with numpy --with pandas --with pyarrow python residual_moran.py PREDICTIONS.parquet ADJACENCY.parquet OUT.csv
"""

import sys

import numpy as np
import pandas as pd

from evaluate import adjacency_matrix


def morans_i(x, W):
    z = np.asarray(x, dtype=float) - np.mean(x)
    den = float((z ** 2).sum())
    s0 = W.sum()
    if den == 0 or s0 == 0:
        return float("nan")
    return float(len(z) / s0 * (z @ W @ z) / den)


def main():
    df = pd.read_parquet(sys.argv[1])
    pairs = pd.read_parquet(sys.argv[2])[["code5_a", "code5_b"]].itertuples(index=False, name=None)
    codes = sorted(df.code5.unique())
    W = adjacency_matrix(pairs, codes)
    rows = []
    for (model, h), g in df.groupby(["model", "h"]):
        vals = []
        for _, gg in g.groupby("target_week"):
            gg = gg.set_index("code5").loc[codes]
            vals.append(morans_i((gg.actual - gg.pred).to_numpy(), W))
        v = np.array([x for x in vals if not np.isnan(x)])
        rows.append({"model": model, "h": h, "weeks_used": len(v), "weeks_total": len(vals), "mean_I": v.mean(), "share_positive": (v > 0).mean()})
    out = pd.DataFrame(rows)
    out.to_csv(sys.argv[3], index=False)
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
