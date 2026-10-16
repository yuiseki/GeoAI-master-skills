"""Check how far a model's uncertainty can be trusted, from out-of-fold predictions.

    calibration  for probabilities (classification): Brier score, expected calibration error
                 (ECE: the share-weighted gap between mean probability and observed frequency in
                 equal-width bins) and the reliability table, overall and by --by
    recalibrate  for probabilities: isotonic or Platt recalibration, cross-fitted (each row's
                 calibrator fitted on the other groups' rows), or fitted on the past only
                 (--time, --calibrate-before) as it would be in use; ECE and Brier before/after
    intervals    for regression: conformal intervals from absolute residuals, and their coverage
                 on rows whose residuals were not used to build them, overall and by --by:
                   role column  split conformal: the quantile of the 'calibration' rows' residuals,
                                applied to the 'test' rows (one model fitted on neither)
                   --time       the quantile of the rows before --calibrate-before, applied to the
                                rows from it on
                   otherwise    each group of --calibrate-by (or of --folds random groups) gets the
                                quantile of the other groups' residuals
                 Building each row's interval from the other rows and measuring coverage on those
                 same rows is not done: without ties that coverage is ceil((1 - alpha) n) / n
                 whatever the model, so it checks nothing.

The input is an out-of-fold predictions file
(--predictions-out: repeat, model, id, target, prediction), joined to a table for --by.

Usage:
    uvx --with duckdb --with scikit-learn python uncertainty.py calibration PREDICTIONS \
        [--table TABLE --id COL --by COL] [--bins 10] [--repeat 0]
    uvx --with duckdb --with scikit-learn python uncertainty.py intervals PREDICTIONS \
        [--table TABLE --id COL --by COL] [--calibrate-by COL | --time COL --calibrate-before T] \
        [--alpha 0.1] [--repeat 0]
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


def _conformal_quantile(residuals, alpha):
    """The ceil((1 - alpha)(m + 1))-th smallest of m absolute residuals; infinite if m is too small."""
    r = np.sort(np.asarray(residuals, float))
    k = math.ceil((1 - alpha) * (len(r) + 1))
    return np.inf if k > len(r) else float(r[k - 1])


def split_intervals(y, pred, calibrate, alpha=0.1):
    """Split conformal: pred +- the conformal quantile of the calibration rows' absolute residuals,
    for the other rows. Calibration rows get NaN. With one model fitted on neither set and rows that
    are exchangeable, a new row is covered with probability between 1 - alpha and
    1 - alpha + 1 / (m + 1)."""
    y, pred, calibrate = np.asarray(y, float), np.asarray(pred, float), np.asarray(calibrate, bool)
    if not calibrate.any() or calibrate.all():
        raise SystemExit("the calibration rows must leave rows on both sides")
    q = _conformal_quantile(np.abs(y[calibrate] - pred[calibrate]), alpha)
    lo, hi = np.full(len(y), np.nan), np.full(len(y), np.nan)
    lo[~calibrate], hi[~calibrate] = pred[~calibrate] - q, pred[~calibrate] + q
    return lo, hi


def held_out_group_intervals(y, pred, groups, alpha=0.1):
    """For each group, pred +- the conformal quantile of the other groups' absolute residuals.
    Coverage then measures how intervals built elsewhere carry over to a group not used to build
    them (an empirical check; with out-of-fold residuals from several fold models no finite-sample
    guarantee is claimed)."""
    y, pred, groups = np.asarray(y, float), np.asarray(pred, float), np.asarray(groups)
    r = np.abs(y - pred)
    q = np.empty(len(y))
    for g in np.unique(groups):
        held = groups == g
        q[held] = _conformal_quantile(r[~held], alpha)
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
    p.add_argument("--calibrate-by", help="intervals: a column of the table; each value's rows get the "
                                          "quantile of the other values' rows")
    p.add_argument("--calibrate-before", type=float)
    p.add_argument("--method", choices=["isotonic", "platt"], default="isotonic")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--bins", type=int, default=10)
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--repeat", type=int, default=0)
    a = p.parse_args()
    if (a.by or a.time or a.calibrate_by) and not (a.table and a.id):
        p.error("--by, --time and --calibrate-by need --table and --id")
    if a.time and a.calibrate_before is None:
        p.error("--time needs --calibrate-before")

    import duckdb

    has_role = "role" in duckdb.sql(f"select * from '{a.predictions}' limit 0").columns
    extra = [f't."{c}"' if c else "null" for c in (a.by, a.time, a.calibrate_by)]
    extra.append("p.role" if has_role else "null")
    src = (f"from '{a.predictions}' p join '{a.table}' t on cast(t.\"{a.id}\" as varchar) = p.id"
           if a.table else f"from '{a.predictions}' p")
    rows = duckdb.sql(f"select p.model, p.target, p.prediction, {', '.join(extra)} {src} "
                      f"where p.repeat = {a.repeat} order by p.model, p.id").fetchall()
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
            if has_role and a.kind == "intervals" and not a.time:
                role = np.array([r[6] for r in sel])
                lo, hi = split_intervals(y, pr, role == "calibration", a.alpha)
                how = "calibrated on the rows with role calibration, scored on the others"
            elif a.time:
                lo, hi = split_intervals(y, pr, t < a.calibrate_before, a.alpha)
                how = "calibrated on the past"
            else:
                held = (np.array([r[5] for r in sel]) if a.calibrate_by
                        else recalibration_groups(len(y), a.folds, 0))
                lo, hi = held_out_group_intervals(y, pr, held, a.alpha)
                how = (f"held out by {a.calibrate_by}" if a.calibrate_by
                       else f"held out by {a.folds} random groups")
            print(f"{model}: {how}")
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
