"""Exploratory (after H1): the autumn bear-report level against several summer weather measures, each tested the
same way (Spearman over prefecture x year, permutation of years within each prefecture, two-sided, 10,000, seed 0).
No direction was fixed, so the p values are listed with the Bonferroni threshold for the number of measures.

Measures (summer = June to August, per prefecture):
    T_now, T_last             max temperature of year y and y-1
    T_yoy                     T_now - T_last (this summer against last summer)
    dT                        T_last - T(y-2) (the H1 measure, for reference)
    SRF_now, SRF_last, SRF_yoy  mean daily solar radiation (AgERA5), same pattern
    P_now, P_last             precipitation (AgERA5 monthly flux, summed over the three months)

Usage:
    uvx --with numpy --with scipy --with pandas python explore_weather.py OUTCOMES.csv SUMMER_TMAX.csv SOLAR_PRECIP.csv OUT.json
"""

import json
import sys

import numpy as np
import pandas as pd

from analysis import demeaned_log, permutation_spearman


def summer_series(sp):
    sp = sp.assign(year=pd.to_datetime(sp.date).dt.year)
    srf = sp[sp.short_id == "AGERA5-SRF"].groupby(["region", "year"]).agg(SRF=("value", "mean"), srf_days=("value", "count")).reset_index()
    pf = sp[sp.short_id == "AGERA5-PF-M"].groupby(["region", "year"]).agg(P=("value", "sum"), p_months=("value", "count")).reset_index()
    return srf.merge(pf, on=["region", "year"], how="outer")


def lagged(df, col):
    df = df.sort_values(["region", "year"])
    g = df.groupby("region")[col]
    return df.assign(**{f"{col}_now": df[col], f"{col}_last": g.shift(1), f"{col}_last2": g.shift(2)})


def main():
    oc, st, sp, out = pd.read_csv(sys.argv[1]), pd.read_csv(sys.argv[2]), pd.read_csv(sys.argv[3]), sys.argv[4]
    w = summer_series(sp)
    print("solar days per summer (min, median, max):", int(w.srf_days.min()), float(w.srf_days.median()), int(w.srf_days.max()),
          "| precipitation months per summer:", sorted(w.p_months.unique().tolist()))
    w = lagged(w, "SRF")
    w = lagged(w, "P")
    t = lagged(st.rename(columns={"summer_tmax_c": "T"}), "T")
    df = oc.merge(t, on=["region", "year"]).merge(w, on=["region", "year"])
    df["T_yoy"] = df.T_now - df.T_last
    df["dT"] = df.T_last - df.T_last2
    df["SRF_yoy"] = df.SRF_now - df.SRF_last
    df["y_autumn"] = demeaned_log(df, "autumn")
    measures = ["T_now", "T_last", "T_yoy", "dT", "SRF_now", "SRF_last", "SRF_yoy", "P_now", "P_last"]
    if df[measures].isna().any().any():
        raise SystemExit(f"missing weather values: {df[measures].isna().sum().to_dict()}")
    res = {"n": int(len(df)), "bonferroni_threshold": 0.05 / len(measures), "measures": {}}
    for m in measures:
        rho, p = permutation_spearman(df[m].to_numpy(), df.y_autumn.to_numpy(), df.region.to_numpy(), alternative="two-sided")
        per = {r: round(float(g[m].corr(g.y_autumn, method="spearman")), 3) for r, g in df.groupby("region")}
        res["measures"][m] = {"rho": rho, "p_two_sided": p, "per_region_rho": per}
        print(f"{m:9s} rho {rho:+.3f}  p {p:.4f}  per region {per}")
    df.to_csv(out.replace(".json", "_table.csv"), index=False)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
