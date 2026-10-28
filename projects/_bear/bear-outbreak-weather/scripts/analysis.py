"""H1 of the plan: is a prefecture's autumn bear-report level (log count, minus the prefecture's mean) related to
dT = summer max temperature of year y-1 minus that of y-2? Plus the planned robustness and falsification checks.

Usage:
    uvx --with numpy --with scipy --with pandas python analysis.py OUTCOMES.csv SUMMER_TMAX.csv OUT.json
"""

import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def with_delta_t(summer):
    s = summer.sort_values(["region", "year"]).copy()
    prev = s.groupby("region").summer_tmax_c.shift(1)
    prev2 = s.groupby("region").summer_tmax_c.shift(2)
    nxt = s.groupby("region").summer_tmax_c.shift(-1)
    # the summers must be consecutive years for the shifts to mean y-1, y-2, y+1
    gap = s.groupby("region").year.diff()
    if (gap.dropna() != 1).any():
        raise ValueError("summers are not consecutive years")
    s["dT"] = prev - prev2
    s["dT_future"] = nxt - s.summer_tmax_c
    s["T_now"] = s.summer_tmax_c
    s["T_last"] = prev
    return s


def demeaned_log(df, col):
    v = np.log(df[col].astype(float) + 1.0)
    return (v - v.groupby(df.region).transform("mean")).to_numpy()


def detrended(df, y):
    out = np.empty(len(df))
    for r, idx in df.groupby("region").indices.items():
        t = df.year.to_numpy()[idx].astype(float)
        b = np.polyfit(t, y[idx], 1)
        out[idx] = y[idx] - np.polyval(b, t)
    return out


def permute_within(y, regions, rng):
    yp = y.copy()
    for r in np.unique(regions):
        idx = np.nonzero(regions == r)[0]
        yp[idx] = y[rng.permutation(idx)]
    return yp


def permutation_spearman(x, y, regions, n=10000, seed=0, alternative="less"):
    rho = spearmanr(x, y).statistic
    rng = np.random.default_rng(seed)
    null = np.array([spearmanr(x, permute_within(y, regions, rng)).statistic for _ in range(n)])
    p = float((np.sum(null <= rho) + 1) / (n + 1)) if alternative == "less" else float((np.sum(np.abs(null) >= abs(rho)) + 1) / (n + 1))
    return float(rho), p


def main():
    out_path = sys.argv[3]
    oc = pd.read_csv(sys.argv[1])
    st = with_delta_t(pd.read_csv(sys.argv[2]))
    df = oc.merge(st, on=["region", "year"], how="left")
    if df.dT.isna().any():
        raise SystemExit(f"rows without dT: {df[df.dT.isna()]}")
    df["y_autumn"] = demeaned_log(df, "autumn")
    df["y_whole"] = demeaned_log(df, "whole")
    res = {"n": int(len(df)), "regions": df.region.value_counts().to_dict()}
    regions = df.region.to_numpy()
    rho, p = permutation_spearman(df.dT.to_numpy(), df.y_autumn.to_numpy(), regions)
    per = {r: float(spearmanr(g.dT, g.y_autumn).statistic) for r, g in df.groupby("region")}
    neg = sum(v < 0 for v in per.values())
    decision = "supported" if (rho < 0 and p < 0.05 and neg >= 3) else ("rejected" if rho >= 0 else "undetermined")
    res["H1"] = {"rho": rho, "p_perm_one_sided": p, "per_region_rho": per, "regions_negative": neg, "decision": decision}
    rho_w, p_w = permutation_spearman(df.dT.to_numpy(), df.y_whole.to_numpy(), regions)
    res["robust_whole_year"] = {"rho": rho_w, "p": p_w}
    ydt = detrended(df, df.y_autumn.to_numpy())
    xdt = detrended(df, df.dT.to_numpy())
    rho_d, p_d = permutation_spearman(xdt, ydt, regions)
    res["robust_detrended"] = {"rho": rho_d, "p": p_d}
    f = df.dropna(subset=["dT_future"])
    rho_f, p_f = permutation_spearman(f.dT_future.to_numpy(), f.y_autumn.to_numpy(), f.region.to_numpy(), alternative="two-sided")
    res["falsification_future_dT"] = {"rho": rho_f, "p_two_sided": p_f, "n": int(len(f))}
    loro = {}
    for r in df.region.unique():
        g = df[df.region != r]
        loro[f"without_{r}"] = float(spearmanr(g.dT, g.y_autumn).statistic)
    res["leave_one_region_out_rho"] = loro
    df.to_csv(out_path.replace(".json", "_table.csv"), index=False)
    json.dump(res, open(out_path, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
