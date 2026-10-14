"""Audit whether recorded counts per unit follow how hard each unit was looked at, rather than the phenomenon.

Per unit: the recorded count, and optionally the area, the exposure (the opportunity for the event: people,
road length, buildings) and the observation effort or its proxy (survey visits, sensors, mapping activity).
Exposure and effort are different things: dividing by people does not correct for how much was observed.

The audit reports, and never corrects:
    rows, missing values per column, zero counts
    per unit: count per area, per exposure, per effort (only the denominators given)
    the rate (per exposure, else per area, else the count) by effort stratum: the distinct effort values when
    there are few, otherwise quantiles. effort_dependent when the rate of the top stratum is 1.5 times the
    bottom one or more (or less than 1 / 1.5), or the Spearman correlation of effort and rate is 0.5 or more
    in size. These are effect sizes; no p-value is given, as effort is usually clustered in space.
    flag per unit: high (2 times or more) or low (half or less) within its own effort stratum, the comparison
    that holds effort fixed
    warnings: effort that moves with exposure (|Spearman| 0.8 or more) may measure opportunity, not observation
    spatial (with x and y): Moran's I of effort and of the rate, with the 8 nearest units
    separable: always False. Without ground truth or a detection model, occurrence and detection are not
    separated; comparisons within an effort stratum are the most that the counts support.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyarrow python audit_observation_bias.py \\
        UNITS ID COUNT [--area COL] [--exposure COL] [--effort COL] [--x COL --y COL] [--quantiles 4] \\
        [--out units.parquet]
"""

import argparse

import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import spearmanr


def rate_of(count, denom):
    if denom is None:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denom > 0, count / denom, np.nan)


def moran(x, xy, k=8):
    ok = ~np.isnan(x)
    x, xy = x[ok], xy[ok]
    if len(x) <= k or np.var(x) == 0:
        return None
    _, nb = cKDTree(xy).query(xy, k + 1)
    z = x - x.mean()
    lag = z[nb[:, 1:]].mean(1)
    return float((z * lag).sum() / (z ** 2).sum())


def strata_of(effort, q):
    vals = np.unique(effort[~np.isnan(effort)])
    if len(vals) <= q:
        return [(v, v) for v in vals]
    edges = np.unique(np.nanquantile(effort, np.linspace(0, 1, q + 1)))
    return list(zip(edges[:-1], edges[1:]))


def audit(ids, count, area=None, exposure=None, effort=None, x=None, y=None, quantiles=4):
    count = np.asarray(count, float)
    arr = {k: (None if v is None else np.asarray(v, float)) for k, v in (("area", area), ("exposure", exposure), ("effort", effort))}
    n = len(ids)
    rep = {"rows": n, "missing": {"count": int(np.isnan(count).sum())}, "zero_counts": int((count == 0).sum()),
           "warnings": [], "separable": False}
    for k, v in arr.items():
        if v is not None:
            rep["missing"][k] = int(np.isnan(v).sum())
    units = {"id": list(ids), "count": count}
    for name, k in (("per_area", "area"), ("per_exposure", "exposure"), ("per_effort", "effort")):
        r = rate_of(count, arr[k])
        if r is not None:
            units[name] = r
    rate = units.get("per_exposure", units.get("per_area", count))
    denom = arr["exposure"] if arr["exposure"] is not None else (arr["area"] if arr["area"] is not None else np.ones(n))
    flag = [""] * n
    rep["by_effort"], rep["effort_dependent"] = [], False
    eff = arr["effort"]
    if eff is not None:
        ok = ~np.isnan(eff) & ~np.isnan(rate)
        rho = spearmanr(eff[ok], rate[ok])[0] if ok.sum() > 2 and np.ptp(eff[ok]) > 0 and np.ptp(rate[ok]) > 0 else 0.0
        rep["effort_rate_spearman"] = float(rho)
        strata = strata_of(eff, quantiles)
        for i, (lo, hi) in enumerate(strata):
            last = i == len(strata) - 1
            s = ok & (eff >= lo) & ((eff <= hi) if last else (eff < hi)) if lo != hi else ok & (eff == lo)
            if not s.any():
                continue
            srate = count[s].sum() / denom[s].sum()
            entry = {"effort": float(lo) if lo == hi else (float(lo), float(hi)), "n": int(s.sum()),
                     "count": float(count[s].sum()), "rate": float(srate)}
            rep["by_effort"].append(entry)
            for j in np.nonzero(s)[0]:
                if srate > 0 and rate[j] >= 2 * srate:
                    flag[j] = "high within its effort stratum"
                elif srate > 0 and rate[j] <= 0.5 * srate:
                    flag[j] = "low within its effort stratum"
        if len(rep["by_effort"]) >= 2:
            lo_r, hi_r = rep["by_effort"][0]["rate"], rep["by_effort"][-1]["rate"]
            ratio = hi_r / lo_r if lo_r > 0 else float("inf")
            rep["top_to_bottom_effort_rate_ratio"] = float(ratio)
            rep["effort_dependent"] = bool(ratio >= 1.5 or ratio <= 1 / 1.5 or abs(rho) >= 0.5)
        if arr["exposure"] is not None:
            okx = ~np.isnan(eff) & ~np.isnan(arr["exposure"])
            if np.ptp(eff[okx]) > 0 and np.ptp(arr["exposure"][okx]) > 0:
                rx = spearmanr(eff[okx], arr["exposure"][okx])[0]
                rep["effort_exposure_spearman"] = float(rx)
                if abs(rx) >= 0.8:
                    rep["warnings"].append(f"effort moves with exposure (Spearman {rx:.2f}): check that the effort column "
                                           "measures observation, not the opportunity for the event")
    units["flag"] = flag
    rep["units"] = units
    if x is not None and y is not None:
        xy = np.column_stack([np.asarray(x, float), np.asarray(y, float)])
        rep["spatial"] = {"rate_moran": moran(np.asarray(rate, float), xy),
                          "effort_moran": moran(eff, xy) if eff is not None else None}
    return rep


def main():
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("units")
    p.add_argument("id")
    p.add_argument("count")
    for a in ("--area", "--exposure", "--effort", "--x", "--y", "--out"):
        p.add_argument(a)
    p.add_argument("--quantiles", type=int, default=4)
    a = p.parse_args()
    cols = [c for c in (a.id, a.count, a.area, a.exposure, a.effort, a.x, a.y) if c]
    con = duckdb.connect()
    con.sql("install httpfs; load httpfs;")
    rows = con.sql("select " + ", ".join(f"\"{c}\"" for c in cols) + f" from '{a.units}'").fetchall()
    col = {c: [r[i] for r in rows] for i, c in enumerate(cols)}

    def num(c):
        return None if not c else np.array([np.nan if v is None else float(v) for v in col[c]])

    rep = audit(col[a.id], num(a.count), num(a.area), num(a.exposure), num(a.effort), num(a.x), num(a.y), a.quantiles)
    print(f"rows {rep['rows']}  missing {rep['missing']}  zero counts {rep['zero_counts']}")
    for k in ("effort_rate_spearman", "top_to_bottom_effort_rate_ratio", "effort_exposure_spearman"):
        if k in rep:
            print(f"{k}: {rep[k]:.3f}")
    for s in rep["by_effort"]:
        print(f"effort {s['effort']}: units {s['n']}  count {s['count']:.0f}  rate {s['rate']:.6g}")
    if "spatial" in rep:
        print(f"Moran's I (8 nearest): effort {rep['spatial']['effort_moran']}, rate {rep['spatial']['rate_moran']}")
    flagged = [(i, f) for i, f in zip(rep["units"]["id"], rep["units"]["flag"]) if f]
    print(f"flagged units ({len(flagged)}): {flagged[:20]}")
    print(f"effort_dependent: {rep['effort_dependent']}  separable: {rep['separable']} (no ground truth, no detection model)")
    for w in rep["warnings"]:
        print("warning:", w)
    if a.out:
        u = rep["units"]
        pq.write_table(pa.table({k: (v if k in ("id", "flag") else [None if np.isnan(z) else float(z) for z in v])
                                 for k, v in u.items()}), a.out)


if __name__ == "__main__":
    main()
