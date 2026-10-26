"""Score a frozen forecast against the reports that came after it (claims C2 and C3, plan block B5).

Inputs: the frozen forecast (model, h, target_week, code5, pred) and the actual weekly counts for the
target weeks, made from a later version of the data by build_table.py (its weekly table, or the form
(code5, target_week, actual)). Build it with --last set to the last COMPLETE week.
Every forecast week must have an actual for every municipality, or the run stops.

C2: per target week, the MAE over municipalities of the candidate minus that of `naive`; the mean over the
weeks with a 90% interval from resampling the weeks (2,000 draws, seed 0). Supported when the mean is
negative and the interval is below 0; rejected when the mean is positive and the interval is above 0;
otherwise undetermined.
C3: per target week, the share of the week's reports that fall in the 5 municipalities the candidate ranks
highest, minus the same for the static ranking `muni_mean`; the same rule with the sign reversed.
Ties are broken by the municipality's code, the same for every model.

Usage:
    uvx --with numpy --with pandas --with pyarrow python score_frozen.py FORECAST.parquet ACTUAL.parquet OUT.json \
        [--candidate hgb_nb]
"""

import argparse
import json

import numpy as np
import pandas as pd

from evaluate import block_bootstrap_interval


def as_actuals(df):
    """Actual counts as (code5, target_week, actual), from either that form or the weekly table of build_table.py."""
    if "week_start" in df.columns:
        df = df.rename(columns={"week_start": "target_week", "bear": "actual"})
    out = df[["code5", "target_week", "actual"]].copy()
    out["target_week"] = out.target_week.astype(str).str[:10]
    return out


def weekly_mae(forecast, actual):
    m = forecast.merge(actual, on=["code5", "target_week"], how="left")
    if m.actual.isna().any():
        raise ValueError(f"{int(m.actual.isna().sum())} forecast rows have no actual count")
    m["err"] = (m.pred - m.actual).abs()
    return m.groupby(["model", "target_week"], as_index=False).err.mean().rename(columns={"err": "mae"})


def weekly_capture(forecast, actual, model, k=5):
    out = {}
    f = forecast[forecast.model == model]
    for week, g in f.groupby("target_week"):
        a = actual[actual.target_week == week].set_index("code5").actual
        g = g.sort_values(["pred", "code5"], ascending=[False, True])
        total = a.sum()
        if total > 0:
            out[week] = float(a.loc[g.code5.iloc[:k]].sum() / total)
    return pd.Series(out)


def _rule(d, lo, hi, better_is_negative):
    mean = float(np.mean(d))
    good, bad = (mean < 0 and hi < 0, mean > 0 and lo > 0) if better_is_negative else (mean > 0 and lo > 0, mean < 0 and hi < 0)
    return "supported" if good else "rejected" if bad else "undetermined"


def decide(forecast, actual, candidate="cand", B=2000, seed=0):
    t = weekly_mae(forecast, actual)
    a = t[t.model == candidate].set_index("target_week").mae
    b = t[t.model == "naive"].set_index("target_week").mae
    d = (a - b).dropna()
    lo, hi = block_bootstrap_interval(d.to_numpy(), np.arange(len(d)), B=B, seed=seed)
    c2 = {"diff": float(d.mean()), "lo": lo, "hi": hi, "n_weeks": int(len(d)), "decision": _rule(d, lo, hi, True)}
    ca = weekly_capture(forecast, actual, candidate)
    cb = weekly_capture(forecast, actual, "muni_mean")
    d3 = (ca - cb).dropna()
    lo3, hi3 = block_bootstrap_interval(d3.to_numpy(), np.arange(len(d3)), B=B, seed=seed)
    c3 = {"diff": float(d3.mean()), "lo": lo3, "hi": hi3, "n_weeks": int(len(d3)), "decision": _rule(d3, lo3, hi3, False),
          "candidate_capture": float(ca.mean()), "static_capture": float(cb.mean())}
    return {"C2": c2, "C3": c3, "mae_by_model": t.groupby("model").mae.mean().to_dict()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forecast")
    ap.add_argument("actual")
    ap.add_argument("out")
    ap.add_argument("--candidate", default="hgb_nb")
    a = ap.parse_args()
    fc = pd.read_parquet(a.forecast)
    act = as_actuals(pd.read_parquet(a.actual))
    weeks = sorted(set(act.target_week))
    fc = fc[fc.target_week.isin(weeks)]
    print(f"{fc.target_week.nunique()} frozen weeks have actuals: {sorted(fc.target_week.unique())}")
    res = decide(fc, act, a.candidate)
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
