"""B1-B3 and the robustness checks of EXPERIMENT_PLAN.md.

uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow python scripts/02_blocks.py

Reads units.parquet and gauge_events.parquet (01_units.py), writes outputs/blocks.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from overfloor import boot_by_day, drop_one_day, share

HERE = Path(__file__).resolve().parent
ART = HERE.parents[3] / "artifacts/_flood/tokyo-overfloor-rain-threshold"
BANDS = [(0, 30), (30, 50), (50, 70), (70, 1e9)]


def ci(vals):
    vals = vals[~np.isnan(vals)]
    return [float(np.percentile(vals, 5)), float(np.percentile(vals, 95))] if len(vals) else [None, None]


def diff_at(cut, mean_of_units=False):
    def f(d):
        hi, lo = d[d["rain"] >= cut], d[d["rain"] < cut]
        if mean_of_units:
            r = lambda x: (x["otf"] / (x["otf"] + x["utf"])).where(x["otf"] + x["utf"] > 0).mean()
            return r(hi) - r(lo)
        return share(hi) - share(lo)
    return f


def bands(d):
    return [{"band": f"{a}-{b if b < 1e9 else ''}", "units": int(((d["rain"] >= a) & (d["rain"] < b)).sum()),
             "days": int(d[(d["rain"] >= a) & (d["rain"] < b)]["day"].nunique()),
             "utf": int(d[(d["rain"] >= a) & (d["rain"] < b)]["utf"].sum()),
             "otf": int(d[(d["rain"] >= a) & (d["rain"] < b)]["otf"].sum()),
             "share": share(d[(d["rain"] >= a) & (d["rain"] < b)])} for a, b in BANDS]


def b1(d, cut=70):
    f = diff_at(cut)
    per = {}
    for p in ("first", "second"):
        x = d[d["period"] == p]
        per[p] = {"d": f(x), "units_ge": int((x["rain"] >= cut).sum()), "days_ge": int(x[x["rain"] >= cut]["day"].nunique())}
    loo = drop_one_day(d, f)
    worst = min(loo, key=lambda k: loo[k])
    r = {"units": len(d), "d": f(d), "ci90": ci(boot_by_day(d, f)), "periods": per,
         "drop_one_day_min": loo[worst], "drop_one_day_min_day": str(pd.Timestamp(worst).date()), "bands": bands(d),
         "bands_by_period": {p: bands(d[d["period"] == p]) for p in ("first", "second")}}
    top = d[d["rain"] >= cut].groupby("day")["otf"].sum().sort_values(ascending=False)
    r["ge_cut_otf_top_days"] = {str(k.date()): int(v) for k, v in top.head(5).items()}
    r["ge_cut_otf_total"] = int(top.sum())
    small = [p for p in per.values() if p["units_ge"] < 5]
    lo, hi = r["ci90"]
    if lo is not None and lo > 0 and not small and all(p["d"] > 0 for p in per.values()) and r["drop_one_day_min"] > 0:
        r["verdict"] = "supported"
    elif (hi is not None and hi <= 0) or any(p["d"] <= 0 for p in per.values() if p["units_ge"] >= 5):
        r["verdict"] = "rejected"
    else:
        r["verdict"] = "undetermined"
    return r


def b2(d):
    def f(x):
        return share(x[x["cls"] == "issui"]) - share(x[x["cls"] == "naisui"])
    x = d[d["ward"] & (d["rain"] < 50) & d["cls"].isin(["issui", "naisui"])]
    per = {p: f(x[x["period"] == p]) for p in ("first", "second")}
    r = {"units": {c: int((x["cls"] == c).sum()) for c in ("issui", "naisui")},
         "share": {c: share(x[x["cls"] == c]) for c in ("issui", "naisui")}, "d": f(x), "ci90": ci(boot_by_day(x, f)),
         "periods": per}
    lo, hi = r["ci90"]
    r["verdict"] = ("supported" if lo > 0 and all(v > 0 for v in per.values()) else
                    "rejected" if hi <= 0 else "undetermined")
    return r


def b3(ge):
    x = ge[ge["rain"] >= 50].copy()
    med = float(x["km"].median())
    x["far"] = x["km"] > med
    x["miss"] = x["jma_max1h"] < 50

    def f(y):
        return y[y["far"]]["miss"].mean() - y[~y["far"]]["miss"].mean()
    r = {"events": len(x), "days": int(x["day"].nunique()), "median_km": med,
         "miss_share": float(x["miss"].mean()), "miss_share_ci90": ci(boot_by_day(x, lambda y: y["miss"].mean())),
         "miss_any_station_share": float((x["jma_any_max1h"] < 50).mean()),
         "near": {"events": int((~x["far"]).sum()), "miss": float(x[~x["far"]]["miss"].mean())},
         "far": {"events": int(x["far"].sum()), "miss": float(x[x["far"]]["miss"].mean())},
         "d": f(x), "ci90": ci(boot_by_day(x, f)),
         "gap_mm_median": float((x["rain"] - x["jma_max1h"]).median())}
    lo, hi = r["ci90"]
    r["verdict"] = "supported" if lo > 0 else "rejected" if hi <= 0 else "undetermined"
    return r


def main():
    u = pd.read_parquet(ART / "units.parquet")
    ge = pd.read_parquet(ART / "gauge_events.parquet")
    wn = u[u["ward"] & (u["cls"] == "naisui") & u["rain"].notna()]
    res = {"B1": b1(wn), "B2": b2(u[u["rain"].notna()]), "B3": b3(ge)}
    rob = {"B1_flag0": b1(wn[wn["nro_flag"] == 0]), "B2_flag0": b2(u[u["rain"].notna() & (u["nro_flag"] == 0)]),
           "B1_cut60": b1(wn, 60), "B1_cut80": b1(wn, 80)}
    f = diff_at(70, mean_of_units=True)
    rob["B1_mean_of_unit_shares"] = {"d": f(wn), "ci90": ci(boot_by_day(wn, f)),
                                     "periods": {p: f(wn[wn["period"] == p]) for p in ("first", "second")}}
    res["robustness"] = {k: (v if k == "B1_mean_of_unit_shares" else
                             {kk: v[kk] for kk in ("d", "ci90", "periods", "verdict") if kk in v}) for k, v in rob.items()}
    out = HERE.parent / "outputs/blocks.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float) + "\n")
    for k in ("B1", "B2", "B3"):
        print(k, res[k]["verdict"], round(res[k]["d"], 3), [round(v, 3) for v in res[k]["ci90"]])


if __name__ == "__main__":
    main()
