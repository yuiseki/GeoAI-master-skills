"""Rank observations by how far they are from what their context leads one to expect.

Contexts:
    time      expected = median of the same unit's values in the --window periods on each side
              (or only before, with --past-only), the row itself excluded
    space     expected = median of the --k nearest other units (great-circle distance); with
              --time, neighbours are taken among rows of the same period
    expected  expected = a column you supply (a model's out-of-fold prediction, a forecast)
    global    no expected value: Isolation Forest and LOF scores on standardised --features

For time, space and expected, the score is |value - expected| / (1.4826 * MAD of all residuals),
a robust z-score that one huge outlier cannot inflate (the mean absolute deviation stands in when
the MAD is 0). For global, the scores are the two
methods' outlier scores (higher is more anomalous) and the ranking is by Isolation Forest.

Usage:
    uvx --with duckdb --with scikit-learn --with pyarrow python find_anomalies.py TABLE ID VALUE \
        --context time --unit COL --time COL [--window 2] [--past-only]
        --context space --lon COL --lat COL [--k 6] [--time COL]
        --context expected --expected COL
        --context global --features F1 F2 ...
        [--top 20] [--out scores.parquet]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knn_neighbors import knn_neighbors  # noqa: E402


def expected_from_time(x, unit, time, window=2, past_only=False):
    x, unit, time = np.asarray(x, float), np.asarray(unit), np.asarray(time)
    exp = np.full(len(x), np.nan)
    for u in np.unique(unit):
        idx = np.flatnonzero(unit == u)
        idx = idx[np.argsort(time[idx], kind="stable")]
        for pos, i in enumerate(idx):
            lo = max(0, pos - window)
            hi = pos if past_only else min(len(idx), pos + window + 1)
            others = [j for j in idx[lo:hi] if j != i]
            if others:
                exp[i] = np.median(x[others])
    return exp


def expected_from_neighbors(x, lon, lat, k=6, time=None):
    x, lon, lat = np.asarray(x, float), np.asarray(lon, float), np.asarray(lat, float)
    exp = np.full(len(x), np.nan)
    groups = [np.arange(len(x))] if time is None else [
        np.flatnonzero(np.asarray(time) == t) for t in np.unique(time)]
    for idx in groups:
        if len(idx) <= k:
            continue
        for i, nb in zip(idx, knn_neighbors(lon[idx], lat[idx], k)):
            exp[i] = np.median(x[idx[nb]])
    return exp


def robust_scale(residuals):
    """1.4826 * MAD of the residuals, or 1.2533 * their mean absolute deviation when more than half
    of them are equal (MAD 0, as with counts that are mostly zero). Returns (scale, which)."""
    r = np.asarray(residuals, float)
    r = r[~np.isnan(r)]
    dev = np.abs(r - np.median(r))
    mad = np.median(dev)
    if mad > 0:
        return 1.4826 * mad, "MAD"
    mean_ad = dev.mean()
    if mean_ad > 0:
        return 1.2533 * mean_ad, "mean absolute deviation (MAD is 0)"
    raise SystemExit("every residual is the same; there is nothing to rank")


def robust_scores(x, expected):
    r = np.asarray(x, float) - np.asarray(expected, float)
    scale, _ = robust_scale(r)
    return np.abs(r) / scale


def global_scores(X, seed=0):
    Z = StandardScaler().fit_transform(np.asarray(X, float))
    iso = IsolationForest(n_estimators=500, random_state=seed).fit(Z)
    lof = LocalOutlierFactor(n_neighbors=min(20, len(Z) - 1)).fit(Z)
    return {"isolation_forest": -iso.score_samples(Z), "lof": -lof.negative_outlier_factor_}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("value")
    p.add_argument("--context", choices=["time", "space", "expected", "global"], required=True)
    p.add_argument("--unit")
    p.add_argument("--time")
    p.add_argument("--window", type=int, default=2)
    p.add_argument("--past-only", action="store_true")
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--k", type=int, default=6)
    p.add_argument("--expected")
    p.add_argument("--features", nargs="+")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out")
    a = p.parse_args()

    import duckdb

    need = {"time": ["unit", "time"], "space": ["lon", "lat"], "expected": ["expected"],
            "global": ["features"]}[a.context]
    for n in need:
        if not getattr(a, n):
            p.error(f"--context {a.context} needs --{n}")
    cols = {"id": a.id, "value": a.value}
    for n in ("unit", "time", "lon", "lat", "expected"):
        if getattr(a, n):
            cols[n] = getattr(a, n)
    for i, f in enumerate(a.features or []):
        cols[f"f{i}"] = f
    t = duckdb.sql("select " + ", ".join(f'"{c}" as {k}' for k, c in cols.items())
                   + f" from '{a.table}'").fetchnumpy()
    for k, v in t.items():
        if np.ma.isMaskedArray(v) and v.mask.any():
            raise SystemExit(f"{cols[k]} has {int(v.mask.sum())} missing values; drop those rows first")
    x = np.asarray(t["value"], float)
    print(f"rows: {len(x)}, value: {a.value}, context: {a.context}")

    if a.context == "global":
        X = np.c_[[np.asarray(t[f"f{i}"], float) for i in range(len(a.features))]].T
        g = global_scores(X, a.seed)
        exp = np.full(len(x), np.nan)
        score = g["isolation_forest"]
        extra = {"lof": g["lof"]}
    else:
        if a.context == "time":
            exp = expected_from_time(x, t["unit"], t["time"], a.window, a.past_only)
        elif a.context == "space":
            exp = expected_from_neighbors(x, t["lon"], t["lat"], a.k, t.get("time"))
        else:
            exp = np.asarray(t["expected"], float)
        score = robust_scores(x, exp)
        print(f"scale of the residuals: {robust_scale(x - exp)[1]}")
        extra = {}
        print(f"rows without an expected value (no neighbours in the context): {int(np.isnan(exp).sum())}")

    order = np.argsort(-np.nan_to_num(score, nan=-np.inf))
    label = "isolation forest score" if a.context == "global" else "robust z"
    print(f"top {a.top} by {label}:")
    for i in order[:a.top]:
        where = "".join(f" {k} {t[k][i]}" for k in ("unit", "time") if k in t)
        line = f"  {str(t['id'][i]):<16}{where}  value {x[i]:.4g}"
        if a.context != "global":
            line += f"  expected {exp[i]:.4g}"
        line += f"  score {score[i]:.3g}" + "".join(f"  {k} {v[i]:.3g}" for k, v in extra.items())
        print(line)

    if a.out:
        import pyarrow as pa

        out = pa.table({"id": [str(v) for v in t["id"]], "value": x, "expected": exp,
                        "score": score, **extra})
        duckdb.sql(f"copy (select * from out order by score desc) to '{a.out}' (format parquet)")
        print(f"scores: {a.out}")


if __name__ == "__main__":
    main()
