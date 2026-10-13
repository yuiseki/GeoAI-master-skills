"""Check how far a model's uncertainty can be trusted, from out-of-fold predictions.

    calibration  for probabilities (classification): Brier score, expected calibration error
                 (ECE: the share-weighted gap between mean probability and observed frequency in
                 equal-width bins) and the reliability table, overall and by --by
    recalibrate  for probabilities: isotonic or Platt recalibration, cross-fitted (each row's
                 calibrator fitted on the other groups' rows), or fitted on the past only
                 (--time, --calibrate-before) as it would be in use; ECE and Brier before/after
    intervals    for regression: split-conformal intervals from the absolute out-of-fold
                 residuals, each row's interval built from the other rows' residuals, or from the
                 past only (--time, --calibrate-before), and their coverage overall and by --by

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
    if len(y) == 0:
        return float("nan")
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


def recalibration_groups(n, folds, seed):
    return np.random.default_rng(seed).permutation(n) % folds


def _calibrator(method, p, y):
    if method == "isotonic":
        from sklearn.isotonic import IsotonicRegression

        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(p, y)
        return iso.predict
    if method == "platt":
        from sklearn.linear_model import LogisticRegression

        def logit(q):
            q = np.clip(q, 1e-6, 1 - 1e-6)
            return np.log(q / (1 - q))[:, None]

        lr = LogisticRegression(C=1e6, max_iter=1000).fit(logit(p), y)
        return lambda q: lr.predict_proba(logit(q))[:, 1]
    raise SystemExit(f"unknown method {method}")


def recalibrate(y, p, method, folds=5, seed=0, time=None, calibrate_before=None):
    """Recalibrated probabilities. Cross-fitted: each row's calibrator is fitted on the other
    groups' rows. With time and calibrate_before: fitted on rows before that time and applied to
    the rows from it on; earlier rows are NaN (no calibrator was fitted without them)."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    out = np.full(len(y), np.nan)
    if time is not None:
        time = np.asarray(time)
        past = time < calibrate_before
        if past.sum() == 0 or past.all():
            raise SystemExit("calibrate_before must leave rows on both sides")
        out[~past] = _calibrator(method, p[past], y[past])(p[~past])
        return out
    groups = recalibration_groups(len(y), folds, seed)
    for g in range(folds):
        held = groups == g
        out[held] = _calibrator(method, p[~held], y[~held])(p[held])
    return out


def conformal_intervals_before(y, pred, time, calibrate_before, alpha=0.1):
    """Split-conformal intervals for the rows from calibrate_before on, from the absolute
    residuals of the rows before it. Earlier rows get NaN."""
    y, pred, time = np.asarray(y, float), np.asarray(pred, float), np.asarray(time)
    past = time < calibrate_before
    r = np.sort(np.abs(y[past] - pred[past]))
    m = len(r)
    k = math.ceil((1 - alpha) * (m + 1))
    q = np.inf if k > m else r[k - 1]
    lo, hi = np.full(len(y), np.nan), np.full(len(y), np.nan)
    lo[~past], hi[~past] = pred[~past] - q, pred[~past] + q
    return lo, hi


def coverage(y, lo, hi):
    y = np.asarray(y, float)
    return float(np.mean((y >= lo) & (y <= hi))) if len(y) else float("nan")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=["calibration", "recalibrate", "intervals"])
    p.add_argument("predictions")
    p.add_argument("--table")
    p.add_argument("--id")
    p.add_argument("--by")
    p.add_argument("--time", help="a column of the table: calibrate on rows before --calibrate-before")
    p.add_argument("--calibrate-before", type=float)
    p.add_argument("--method", choices=["isotonic", "platt"], default="isotonic")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--bins", type=int, default=10)
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--repeat", type=int, default=0)
    a = p.parse_args()
    if (a.by or a.time) and not (a.table and a.id):
        p.error("--by and --time need --table and --id")
    if a.time and a.calibrate_before is None:
        p.error("--time needs --calibrate-before")

    import duckdb

    extra = [f't."{c}"' if c else "null" for c in (a.by, a.time)]
    src = (f"from '{a.predictions}' p join '{a.table}' t on cast(t.\"{a.id}\" as varchar) = p.id"
           if a.table else f"from '{a.predictions}' p")
    rows = duckdb.sql(f"select p.model, p.target, p.prediction, {extra[0]}, {extra[1]} {src} "
                      f"where p.repeat = {a.repeat} order by p.model").fetchall()
    if not rows:
        raise SystemExit(f"no predictions for repeat {a.repeat}")
    models = sorted({r[0] for r in rows})
    print(f"predictions: {a.predictions}, repeat {a.repeat}, models: {models}")
    if a.time:
        print(f"calibrated on {a.time} < {a.calibrate_before:g}, scored on the rows from it on")

    for model in models:
        sel = [r for r in rows if r[0] == model]
        y = np.array([r[1] for r in sel], float)
        pr = np.array([r[2] for r in sel], float)
        g = np.array([r[3] for r in sel]) if a.by else None
        t = np.array([r[4] for r in sel], float) if a.time else None
        if a.kind == "calibration":
            tab = calibration_table(y, pr, a.bins)
            print(f"{model}: n {tab['n']}, Brier {tab['brier']:.4f}, ECE {tab['ece']:.4f}")
            for b in tab["bins"]:
                print(f"    {b['bin']}: n {b['n']:>6}, mean p {b['mean_p']:.3f}, observed {b['observed']:.3f}")
            if a.by:
                for v in np.unique(g):
                    m = g == v
                    tg = calibration_table(y[m], pr[m], a.bins)
                    print(f"  {a.by} {v}: n {tg['n']}, mean p {pr[m].mean():.3f}, "
                          f"observed {y[m].mean():.3f}, ECE {tg['ece']:.4f}")
        elif a.kind == "recalibrate":
            cal = recalibrate(y, pr, a.method, a.folds, 0, t, a.calibrate_before)
            m = ~np.isnan(cal)
            before, after = calibration_table(y[m], pr[m], a.bins), calibration_table(y[m], cal[m], a.bins)
            how = "on the past" if a.time else f"cross-fitted over {a.folds} groups"
            print(f"{model}: {a.method} {how}, n {int(m.sum())}: ECE {before['ece']:.4f} -> "
                  f"{after['ece']:.4f}, Brier {before['brier']:.4f} -> {after['brier']:.4f}")
            if a.by:
                for v in np.unique(g[m]):
                    mm = m & (g == v)
                    print(f"  {a.by} {v}: n {int(mm.sum())}, ECE {ece(y[mm], pr[mm], a.bins):.4f} -> "
                          f"{ece(y[mm], cal[mm], a.bins):.4f}")
        else:
            if a.time:
                lo, hi = conformal_intervals_before(y, pr, t, a.calibrate_before, a.alpha)
            else:
                lo, hi = conformal_intervals(y, pr, a.alpha)
            m = ~np.isnan(lo)
            width = float(np.median(hi[m] - lo[m]))
            print(f"{model}: n {int(m.sum())}, promised {1 - a.alpha:.0%}, "
                  f"covered {coverage(y[m], lo[m], hi[m]):.3f}, median width {width:.4g}")
            if a.by:
                for v in np.unique(g[m]):
                    mm = m & (g == v)
                    print(f"  {a.by} {v}: n {int(mm.sum())}, covered {coverage(y[mm], lo[mm], hi[mm]):.3f}")


if __name__ == "__main__":
    main()
