"""Travel time reliability of road links from observed travel times: LOTTR (FHWA), TTI, PTI and delay per link and
period, the difference between two periods with an interval from resampling days, and a ranking of bottlenecks.

    uvx --with pandas --with numpy --with pyarrow python ttr_metrics.py OBS.parquet OUTDIR [--compare AM PM] \
        [--holidays 2026-10-12 ...] [--min-days 10]

OBS.parquet: link, time (local clock time of the road, no zone), travel_time_s. Rows with a missing, zero or
negative travel time are counted as invalid and dropped.

Definitions (the FHWA rule for the national performance measure, 23 CFR 490.511, unless said):
  bins      the mean travel time of each link in each 15-minute bin of each day (the FHWA unit)
  periods   AM weekdays 06:00-10:00, MIDD weekdays 10:00-16:00, PM weekdays 16:00-20:00, WE weekends and holidays
            06:00-20:00. Other bins belong to no period
  LOTTR     80th / 50th percentile of the link's bin travel times in the period (linear interpolation, as
            Excel's PERCENTILE.INC); a link is reliable when the LOTTR of every period is below 1.5
  free flow the 15th percentile of the link's bin travel times between 00:00 and 05:00 on any day (an 85th
            percentile speed). Not an FHWA rule: posted speeds or an agency's free-flow speed may differ
  TTI       mean bin travel time in the period / free flow (Travel Time Index, as in the Urban Mobility Report)
  PTI       95th percentile / free flow (Planning Time Index)
  delay_s   mean bin travel time - free flow, per trip on the link. Vehicle hours of delay need volumes, which
            these data do not have

Writes OUTDIR/metrics.csv (link, period, bins, days, p50, p80, p95, mean, free_flow_s, lottr, tti, pti, delay_s),
OUTDIR/compare.csv (link, mean of A, mean of B, diff_s = B - A, lo, hi over days) and OUTDIR/audit.json.
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

PERIODS = {"AM": (6, 10), "MIDD": (10, 16), "PM": (16, 20)}
WEEKEND = (6, 20)
NIGHT = (0, 5)


def period_of(times, holidays=()):
    times = pd.DatetimeIndex(times)
    hol = set(holidays)
    out = []
    for t in times:
        h = t.hour
        weekend = t.day_of_week >= 5 or t.date() in hol
        if weekend:
            out.append("WE" if WEEKEND[0] <= h < WEEKEND[1] else None)
            continue
        out.append(next((p for p, (a, b) in PERIODS.items() if a <= h < b), None))
    return pd.Series(out, dtype=object)


def bin15(df):
    """Mean travel time per link and 15-minute bin, and the count of every input row."""
    rows = len(df)
    ok = df["travel_time_s"].notna() & (df["travel_time_s"] > 0) & df["time"].notna()
    d = df.loc[ok, ["link", "time", "travel_time_s"]].copy()
    d["bin"] = pd.DatetimeIndex(d["time"]).floor("15min")
    b = d.groupby(["link", "bin"], as_index=False)["travel_time_s"].mean()
    return b, {"rows": rows, "invalid": int((~ok).sum()), "used": int(ok.sum()), "bins": len(b)}


def free_flow(b):
    h = pd.DatetimeIndex(b["bin"]).hour
    night = b[(h >= NIGHT[0]) & (h < NIGHT[1])]
    return night.groupby("link")["travel_time_s"].quantile(0.15).to_dict()


def metrics(b, holidays=()):
    b = b.copy()
    b["period"] = period_of(b["bin"], holidays).values
    b["day"] = pd.DatetimeIndex(b["bin"]).date
    ff = free_flow(b)
    rows = []
    for (link, per), g in b[b["period"].notna()].groupby(["link", "period"]):
        tt = g["travel_time_s"].to_numpy()
        p50, p80, p95 = np.percentile(tt, [50, 80, 95])
        mean = tt.mean()
        f = ff.get(link, np.nan)
        rows.append({"link": link, "period": per, "bins": len(tt), "days": g["day"].nunique(), "p50": p50,
                     "p80": p80, "p95": p95, "mean": mean, "free_flow_s": f, "lottr": p80 / p50,
                     "tti": mean / f, "pti": p95 / f, "delay_s": mean - f})
    return pd.DataFrame(rows)


def compare_periods(b, a, z, reps=1000, seed=0, holidays=()):
    """Per link: mean over days of the day's mean travel time in period z minus that in period a, with a 95%
    interval from resampling the days that have both."""
    b = b.copy()
    b["period"] = period_of(b["bin"], holidays).values
    b["day"] = pd.DatetimeIndex(b["bin"]).date
    day = b[b["period"].isin([a, z])].groupby(["link", "day", "period"])["travel_time_s"].mean().unstack("period")
    rng = np.random.default_rng(seed)
    rows = []
    for link, g in day.groupby(level="link"):
        g = g.dropna()
        if g.empty or a not in g or z not in g:
            continue
        d = (g[z] - g[a]).to_numpy()
        boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(reps)]
        rows.append({"link": link, "days": len(d), f"mean_{a}": g[a].mean(), f"mean_{z}": g[z].mean(),
                     "diff_s": d.mean(), "lo": float(np.percentile(boots, 2.5)), "hi": float(np.percentile(boots, 97.5))})
    return pd.DataFrame(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("obs")
    p.add_argument("outdir")
    p.add_argument("--compare", nargs=2, default=["AM", "PM"])
    p.add_argument("--holidays", nargs="*", default=[])
    p.add_argument("--min-days", type=int, default=10, help="periods with fewer days are flagged, not dropped")
    a = p.parse_args(argv)
    hol = [pd.Timestamp(h).date() for h in a.holidays]
    df = pd.read_parquet(a.obs)
    b, audit = bin15(df)
    m = metrics(b, hol)
    m["few_days"] = m["days"] < a.min_days
    os.makedirs(a.outdir, exist_ok=True)
    m.to_csv(os.path.join(a.outdir, "metrics.csv"), index=False, float_format="%.4f")
    c = compare_periods(b, *a.compare, holidays=hol)
    c.to_csv(os.path.join(a.outdir, "compare.csv"), index=False, float_format="%.2f")
    rel = m.groupby("link")["lottr"].max()
    audit.update(links=int(b["link"].nunique()), links_with_free_flow=int(m.dropna(subset=["free_flow_s"])["link"].nunique()),
                 unreliable_links=int((rel >= 1.5).sum()), compare=a.compare, holidays=a.holidays)
    with open(os.path.join(a.outdir, "audit.json"), "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=1)
    print(json.dumps(audit))


if __name__ == "__main__":
    sys.exit(main())
