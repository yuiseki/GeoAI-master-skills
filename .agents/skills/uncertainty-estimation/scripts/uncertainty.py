"""Check how far a model's uncertainty can be trusted, from out-of-fold predictions.

    calibration  for probabilities (classification): Brier score, expected calibration error
                 (ECE: the share-weighted gap between mean probability and observed frequency in
                 equal-width bins) and the reliability table, overall and by --by
    intervals    for regression: split-conformal intervals from the absolute out-of-fold
                 residuals, each row's interval built from the other rows' residuals, and their
                 coverage overall and by --by

The input is the predictions file of spatial-data-modeling/scripts/compare_models.py
(--predictions-out: repeat, model, id, target, prediction), joined to a table for --by.

Usage:
    uvx --with duckdb --with scikit-learn python uncertainty.py calibration PREDICTIONS \
        [--table TABLE --id COL --by COL] [--bins 10] [--repeat 0]
    uvx --with duckdb --with scikit-learn python uncertainty.py intervals PREDICTIONS \
        [--table TABLE --id COL --by COL] [--alpha 0.1] [--repeat 0]
"""

import argparse
import math

import numpy as np


def _bin_index(p, bins):
    return np.minimum((np.asarray(p, float) * bins).astype(int), bins - 1)


def ece(y, p, bins=10):
    y, p = np.asarray(y, float), np.asarray(p, float)
    idx = _bin_index(p, bins)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(total)


def calibration_table(y, p, bins=10):
    y, p = np.asarray(y, float), np.asarray(p, float)
    idx = _bin_index(p, bins)
    rows = []
    for b in range(bins):
        m = idx == b
        if m.any():
            rows.append({"bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "n": int(m.sum()),
                         "mean_p": float(p[m].mean()), "observed": float(y[m].mean())})
    return {"n": len(y), "brier": float(np.mean((p - y) ** 2)), "ece": ece(y, p, bins),
            "bins": rows}


def conformal_intervals(y, pred, alpha=0.1):
    """For each row, pred +- the ceil((1 - alpha)(m + 1))-th smallest absolute residual of the
    m = n - 1 other rows (split conformal, the row's own residual left out)."""
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    r = np.abs(y - pred)
    n = len(r)
    m = n - 1
    k = math.ceil((1 - alpha) * (m + 1))
    order = np.sort(r)
    q = np.empty(n)
    if k > m:
        q[:] = np.inf  # too few rows for this alpha: the interval is unbounded
    else:
        # The k-th smallest of the others is the k-th smallest overall, unless the row's own
        # residual is among the k smallest, in which case it is the (k+1)-th. With ties at the
        # k-th value the (k+1)-th equals it, so the rule holds.
        kth, k1th = order[k - 1], order[k] if k < n else np.inf
        q = np.where(r <= kth, k1th, kth)
    return pred - q, pred + q


def coverage(y, lo, hi):
    y = np.asarray(y, float)
    return float(np.mean((y >= lo) & (y <= hi))) if len(y) else float("nan")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=["calibration", "intervals"])
    p.add_argument("predictions")
    p.add_argument("--table")
    p.add_argument("--id")
    p.add_argument("--by")
    p.add_argument("--bins", type=int, default=10)
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--repeat", type=int, default=0)
    a = p.parse_args()
    if a.by and not (a.table and a.id):
        p.error("--by needs --table and --id")

    import duckdb

    by_sql = (f", t.\"{a.by}\" as g from '{a.predictions}' p join '{a.table}' t "
              f"on cast(t.\"{a.id}\" as varchar) = p.id") if a.by else f", null as g from '{a.predictions}' p"
    rows = duckdb.sql(f"select p.model, p.target, p.prediction{by_sql} "
                      f"where p.repeat = {a.repeat} order by p.model").fetchall()
    if not rows:
        raise SystemExit(f"no predictions for repeat {a.repeat}")
    models = sorted({r[0] for r in rows})
    print(f"predictions: {a.predictions}, repeat {a.repeat}, models: {models}")

    for model in models:
        sel = [r for r in rows if r[0] == model]
        y = np.array([r[1] for r in sel], float)
        pr = np.array([r[2] for r in sel], float)
        g = np.array([r[3] for r in sel]) if a.by else None
        if a.kind == "calibration":
            t = calibration_table(y, pr, a.bins)
            print(f"{model}: n {t['n']}, Brier {t['brier']:.4f}, ECE {t['ece']:.4f}")
            for b in t["bins"]:
                print(f"    {b['bin']}: n {b['n']:>6}, mean p {b['mean_p']:.3f}, observed {b['observed']:.3f}")
            if a.by:
                for v in np.unique(g):
                    m = g == v
                    tg = calibration_table(y[m], pr[m], a.bins)
                    print(f"  {a.by} {v}: n {tg['n']}, mean p {pr[m].mean():.3f}, "
                          f"observed {y[m].mean():.3f}, ECE {tg['ece']:.4f}")
        else:
            lo, hi = conformal_intervals(y, pr, a.alpha)
            width = float(np.median(hi - lo))
            print(f"{model}: n {len(y)}, promised {1 - a.alpha:.0%}, covered {coverage(y, lo, hi):.3f},"
                  f" median width {width:.4g}")
            if a.by:
                for v in np.unique(g):
                    m = g == v
                    print(f"  {a.by} {v}: n {int(m.sum())}, covered {coverage(y[m], lo[m], hi[m]):.3f}")


if __name__ == "__main__":
    main()
