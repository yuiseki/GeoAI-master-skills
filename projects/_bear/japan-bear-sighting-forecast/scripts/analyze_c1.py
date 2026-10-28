"""Claim C1 on a table of predictions from evaluate.py: are the same-period-last-year forecast and the
long-run mean worse than the last value?

For each horizon, the MAE over the municipalities is taken per origin, the difference to `naive` is paired by
origin, and the mean difference gets a 90% interval from resampling whole calendar years of the origin
(2,000 draws, seed 0). The rule of EXPERIMENT_PLAN.md (B4) judges horizon 1 only: supported when both
differences are positive with an interval above 0; not supported when either interval lies entirely
at or below 0 or either difference is not positive; otherwise undetermined. Horizons 2 and 3 are reported
as direction only.

Usage:
    uvx --with numpy --with pandas --with pyarrow python analyze_c1.py PREDICTIONS.parquet [OUT.json]
"""

import json
import sys

import numpy as np
import pandas as pd

from evaluate import block_bootstrap_interval


def per_origin_mae(df):
    g = df.assign(err=(df.pred - df.actual).abs()).groupby(["model", "h", "origin_week"], as_index=False).err.mean()
    g = g.rename(columns={"err": "mae"})
    g["year"] = g.origin_week.str[:4].astype(int)
    return g


def _diff(t, model, h, base="naive"):
    a = t[(t.model == model) & (t.h == h)].set_index("origin_week")
    b = t[(t.model == base) & (t.h == h)].set_index("origin_week")
    idx = a.index.intersection(b.index)
    return (a.loc[idx, "mae"] - b.loc[idx, "mae"]).to_numpy(), a.loc[idx, "year"].to_numpy()


def c1_decision(t, B=2000, seed=0, horizon=1, others=("seasonal_naive", "muni_mean")):
    res = {}
    for m in others:
        d, years = _diff(t, m, horizon)
        lo, hi = block_bootstrap_interval(d, years, B=B, seed=seed, level=0.90)
        res[m] = {"diff": float(d.mean()), "lo": lo, "hi": hi, "n_origins": int(len(d))}
    if all(v["diff"] > 0 and v["lo"] > 0 for v in res.values()):
        res["decision"] = "supported"
    elif any(v["diff"] <= 0 or v["hi"] <= 0 for v in res.values()):
        res["decision"] = "not supported"
    else:
        res["decision"] = "undetermined"
    return res


def main():
    df = pd.read_parquet(sys.argv[1])
    t = per_origin_mae(df)
    out = {"horizon1": c1_decision(t), "other_horizons_direction_only": {}}
    for h in sorted(t.h.unique()):
        if h == 1:
            continue
        out["other_horizons_direction_only"][f"h{h}"] = {
            m: float(_diff(t, m, h)[0].mean()) for m in ("seasonal_naive", "muni_mean")
        }
    print(json.dumps(out, indent=1, ensure_ascii=False))
    if len(sys.argv) > 2:
        json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
