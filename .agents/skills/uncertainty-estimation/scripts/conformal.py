"""Prediction intervals with a finite-sample guarantee that fit their own models: CV+ and conformalised quantile
regression (CQR).

    cv-plus  K fold models; each training row i gives its out-of-fold absolute residual R_i and its fold model's
             prediction mu_k(i)(x) at a new row. The interval is
                 [ floor(alpha (n + 1))-th smallest of mu_k(i)(x) - R_i ,  ceil((1 - alpha)(n + 1))-th smallest of
                   mu_k(i)(x) + R_i ]
             (Barber, Candes, Ramdas, Tibshirani, "Predictive inference with the jackknife+", Annals of
             Statistics 2021). If the training and new rows are exchangeable, a new row is covered with
             probability at least 1 - 2 alpha (about 1 - alpha in practice), whatever the model, even an unstable
             one. Its width is the same everywhere up to the fold models' spread.
    cqr      two quantile models (alpha / 2 and 1 - alpha / 2) fitted on the 'train' rows; on the 'calibration'
             rows the score max(lower - y, y - upper); the interval is [lower - Q, upper + Q] with Q the
             ceil((1 - alpha)(m + 1))-th smallest score (Romano, Patterson, Candes, "Conformalized quantile
             regression", NeurIPS 2019). Guarantee 1 - alpha under the same exchangeability, and the width
             follows the quantile models: wide where the noise is large. The correction Q is the same for every
             row: if the quantile models under-cover everywhere (they overfit), adding one Q over-covers where
             they are narrow and under-covers where they are wide. --scaled divides the score by the width
             (CQR-r) so the correction grows with it.

--mondrian COL calibrates within each value of COL (Mondrian conformal prediction, Vovk et al. 2005): coverage
is then promised per value, given exchangeability within it; a value with few rows gets a wide or infinite
interval. Without it, both guarantees are marginal (averaged over all rows), not per region or per row, and both need the new rows to
come from the same process as the training rows. Rows near each other in space or time are not exchangeable
with rows far away: hold out whole regions or periods (--test-by) to see what the interval does there.

Usage:
    uvx --with duckdb --with numpy --with scikit-learn --with pyarrow python conformal.py {cv-plus,cqr} TABLE --target Y \\
        --features A,B,C (--role COL | --test-by COL) [--fold-by COL | --folds 5] [--model linear|hgb] \\
        [--alpha 0.1] [--scaled] [--mondrian COL] [--by COL] [--id COL] [--where SQL] [--out intervals.parquet]
    --role: cv-plus reads 'train' and 'test'; cqr reads 'train', 'calibration' and 'test'.
    --test-by: each value's rows in turn are the test rows, the others the training rows (cqr puts every
    --calibration-every-th of them in calibration, default 3).
"""

import argparse
import math

import numpy as np


def rank_quantile(v, alpha, upper=True):
    """The finite-sample conformal order statistic of v: the ceil((1 - alpha)(n + 1))-th smallest (upper; +inf
    when beyond n) or the floor(alpha (n + 1))-th smallest (lower; -inf when 0). Along axis 0."""
    v = np.sort(np.asarray(v, float), axis=0)
    n = v.shape[0]
    if upper:
        k = math.ceil((1 - alpha) * (n + 1))
        return v[k - 1] if k <= n else np.full(v.shape[1:], np.inf) if v.ndim > 1 else np.inf
    k = math.floor(alpha * (n + 1))
    return v[k - 1] if k >= 1 else np.full(v.shape[1:], -np.inf) if v.ndim > 1 else -np.inf


def cv_plus(residuals, fold, test_pred, alpha=0.1, groups=None, test_groups=None):
    """residuals (n,) out-of-fold |y - prediction|; fold (n,) each row's fold index; test_pred (K, m) fold k's
    model's predictions at the m new rows. groups / test_groups (Mondrian): each new row's interval uses only
    the training rows of its own group (infinite when the group has too few)."""
    residuals = np.asarray(residuals, float)
    test_pred = np.asarray(test_pred, float)
    fold = np.asarray(fold)
    if groups is None:
        at = test_pred[fold]  # (n, m): row i's fold model at each new row
        return (rank_quantile(at - residuals[:, None], alpha, upper=False),
                rank_quantile(at + residuals[:, None], alpha, upper=True))
    groups, test_groups = np.asarray(groups), np.asarray(test_groups)
    lo, hi = np.empty(test_pred.shape[1]), np.empty(test_pred.shape[1])
    for g in np.unique(test_groups):
        mine, rows = test_groups == g, groups == g
        at = test_pred[fold[rows]][:, mine]
        lo[mine] = rank_quantile(at - residuals[rows, None], alpha, upper=False)
        hi[mine] = rank_quantile(at + residuals[rows, None], alpha, upper=True)
    return lo, hi


def cqr(y_cal, lo_cal, hi_cal, lo_test, hi_test, alpha=0.1, scaled=False, groups=None, test_groups=None):
    """scaled: divide each score by its interval's width, and widen each new interval in proportion to its own
    width (Sesia and Candes 2020's CQR-r): the correction then follows the noise too. groups / test_groups
    (Mondrian): each new row's correction comes from the calibration rows of its own group."""
    y_cal, lo_cal, hi_cal = (np.asarray(v, float) for v in (y_cal, lo_cal, hi_cal))
    lo_test, hi_test = np.asarray(lo_test, float), np.asarray(hi_test, float)
    if groups is not None:
        groups, test_groups = np.asarray(groups), np.asarray(test_groups)
        lo, hi = np.empty(len(lo_test)), np.empty(len(lo_test))
        for g in np.unique(test_groups):
            c, t = groups == g, test_groups == g
            lo[t], hi[t] = cqr(y_cal[c], lo_cal[c], hi_cal[c], lo_test[t], hi_test[t], alpha, scaled)
        return lo, hi
    score = np.maximum(lo_cal - y_cal, y_cal - hi_cal)
    if not scaled:
        q = rank_quantile(score, alpha, upper=True)
        return lo_test - q, hi_test + q
    # Where the two quantile models cross, swap them (rearrangement, Chernozhukov et al. 2010): the scaled score
    # needs a positive width.
    lo_cal, hi_cal = np.minimum(lo_cal, hi_cal), np.maximum(lo_cal, hi_cal)
    lo_test, hi_test = np.minimum(lo_test, hi_test), np.maximum(lo_test, hi_test)
    score = np.maximum(lo_cal - y_cal, y_cal - hi_cal)
    w_cal, w_test = hi_cal - lo_cal, hi_test - lo_test
    if (w_cal <= 0).any() or (w_test <= 0).any():
        raise ValueError("the quantile models give zero width on some rows; the scaled score needs a width")
    q = rank_quantile(score / w_cal, alpha, upper=True)
    return lo_test - q * w_test, hi_test + q * w_test


def _model(model, quantile=None):
    from sklearn.base import clone

    if not isinstance(model, str):
        return clone(model)
    if model == "linear":
        from sklearn.linear_model import LinearRegression, QuantileRegressor

        return LinearRegression() if quantile is None else QuantileRegressor(quantile=quantile, alpha=0.0,
                                                                             solver="highs")
    if model == "hgb":
        from sklearn.ensemble import HistGradientBoostingRegressor

        return (HistGradientBoostingRegressor(random_state=0) if quantile is None else
                HistGradientBoostingRegressor(loss="quantile", quantile=quantile, random_state=0))
    raise ValueError(f"unknown model {model}")


def fit_cv_plus(X, y, X_test, folds, model="linear", alpha=0.1, groups=None, test_groups=None):
    X, y, X_test, folds = np.asarray(X, float), np.asarray(y, float), np.asarray(X_test, float), np.asarray(folds)
    keys = np.unique(folds)
    index = np.searchsorted(keys, folds)
    residuals = np.empty(len(y))
    test_pred = np.empty((len(keys), len(X_test)))
    for k in range(len(keys)):
        m = index == k
        f = _model(model).fit(X[~m], y[~m])
        residuals[m] = np.abs(y[m] - f.predict(X[m]))
        test_pred[k] = f.predict(X_test)
    return cv_plus(residuals, index, test_pred, alpha, groups, test_groups)


def fit_cqr(X, y, role, X_test, model="hgb", alpha=0.1, scaled=False, raw=None, groups=None, test_groups=None):
    """raw: a dict that gets the quantile models' own coverage of the calibration rows, before the correction."""
    X, y, X_test, role = np.asarray(X, float), np.asarray(y, float), np.asarray(X_test, float), np.asarray(role)
    tr, cal = role == "train", role == "calibration"
    if not cal.any() or not tr.any():
        raise ValueError("cqr needs 'train' and 'calibration' rows")
    lo_m = _model(model, alpha / 2).fit(X[tr], y[tr])
    hi_m = _model(model, 1 - alpha / 2).fit(X[tr], y[tr])
    lc, hc = lo_m.predict(X[cal]), hi_m.predict(X[cal])
    lt, ht = lo_m.predict(X_test), hi_m.predict(X_test)
    if raw is not None:
        raw.setdefault("crossed", []).append(int((hc < lc).sum() + (ht < lt).sum()))
        raw.setdefault("covered", []).append(int(((y[cal] >= lc) & (y[cal] <= hc)).sum()))
        raw.setdefault("rows", []).append(int(cal.sum()))
    return cqr(y[cal], lc, hc, lt, ht, alpha, scaled, None if groups is None else np.asarray(groups)[cal],
               test_groups)


def _report(y, lo, hi, by, alpha):
    cover = (y >= lo) & (y <= hi)
    width = hi - lo
    print(f"rows {len(y)}: coverage {cover.mean():.3f} (promised {1 - alpha:g}), "
          f"median width {np.median(width):.4g}, infinite {int(np.isinf(width).sum())}")
    if by is not None:
        for g in sorted(set(by), key=str):
            m = by == g
            print(f"  {g}: rows {int(m.sum())}, coverage {cover[m].mean():.3f}, median width {np.median(width[m]):.4g}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=["cv-plus", "cqr"])
    p.add_argument("table")
    p.add_argument("--target", required=True)
    p.add_argument("--features", required=True)
    p.add_argument("--role")
    p.add_argument("--test-by")
    p.add_argument("--fold-by")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--calibration-every", type=int, default=3)
    p.add_argument("--model", choices=["linear", "hgb"], default=None)
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--scaled", action="store_true", help="cqr: scale the correction by each interval's width")
    p.add_argument("--mondrian", help="a column: each row's interval is calibrated on rows of its own value only "
                                      "(coverage promised per value; infinite where a value has too few rows)")
    p.add_argument("--by")
    p.add_argument("--id")
    p.add_argument("--where", default="true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out")
    a = p.parse_args()
    if bool(a.role) == bool(a.test_by):
        p.error("give one of --role and --test-by")
    model = a.model or ("linear" if a.kind == "cv-plus" else "hgb")

    import duckdb

    feats = [f.strip() for f in a.features.split(",")]
    extra = [c for c in (a.role, a.test_by, a.fold_by, a.by, a.id, a.mondrian) if c]
    cols = ", ".join(f'"{c}"' for c in [a.target, *feats, *dict.fromkeys(extra)])
    rel = duckdb.sql(f"select {cols} from '{a.table}' where {a.where}")
    df = {c: np.array(v) for c, v in zip(rel.columns, zip(*rel.fetchall()))}
    n_all = len(df[a.target])
    X = np.column_stack([df[f].astype(float) for f in feats])
    y = df[a.target].astype(float)
    ok = ~np.isnan(X).any(1) & ~np.isnan(y)
    print(f"rows {n_all}; dropped for a missing target or feature {int((~ok).sum())}; used {int(ok.sum())}")
    X, y = X[ok], y[ok]
    col = {c: df[c][ok] for c in extra}
    rng = np.random.default_rng(a.seed)

    def folds_of(m):
        if a.fold_by:
            return col[a.fold_by][m]
        return rng.permutation(np.arange(int(m.sum())) % a.folds)

    gr = col[a.mondrian] if a.mondrian else None

    def one(train, test):
        gtr, gte = (None, None) if gr is None else (gr[train], gr[test])
        if a.kind == "cv-plus":
            return fit_cv_plus(X[train], y[train], X[test], folds_of(train), model, a.alpha, gtr, gte)
        idx = rng.permutation(int(train.sum()))
        role = np.where(idx % a.calibration_every == 0, "calibration", "train")
        return fit_cqr(X[train], y[train], role, X[test], model, a.alpha, a.scaled, raw, gtr, gte)

    lo, hi = np.full(len(y), np.nan), np.full(len(y), np.nan)
    raw = {}
    if a.role:
        r = col[a.role].astype(str)
        test = r == "test"
        if a.kind == "cv-plus":
            train = r == "train"
            l, h = one(train, test)
        else:
            train = np.isin(r, ["train", "calibration"])
            l, h = fit_cqr(X[train], y[train], r[train], X[test], model, a.alpha, a.scaled, raw,
                           None if gr is None else gr[train], None if gr is None else gr[test])
        unused = int((~train & ~test).sum())
        print(f"train {int(train.sum())}, test {int(test.sum())}, other roles {unused} (left out)")
        lo[test], hi[test] = l, h
    else:
        g = col[a.test_by]
        for v in sorted(set(g), key=str):
            test = g == v
            lo[test], hi[test] = one(~test, test)
        print(f"each of {len(set(g))} values of {a.test_by} held out in turn")
    m = ~np.isnan(lo)
    print(f"{a.kind}, model {model}, alpha {a.alpha:g}" + (", scaled" if a.scaled else "")
          + (f", calibrated within each value of {a.mondrian}" if a.mondrian else ""))
    if raw:
        print(f"the quantile models alone covered {sum(raw['covered'])} of {sum(raw['rows'])} calibration rows "
              f"({sum(raw['covered']) / sum(raw['rows']):.3f}) before the correction; rows where they cross "
              f"(upper below lower) {sum(raw['crossed'])}" + (" (swapped)" if a.scaled else ""))
    _report(y[m], lo[m], hi[m], col[a.by][m] if a.by else None, a.alpha)
    if a.out:
        import pyarrow as pa
        import pyarrow.parquet as pq

        out = {"target": y[m], "lower": lo[m], "upper": hi[m]}
        if a.id:
            out = {"id": col[a.id][m], **out}
        pq.write_table(pa.table(out), a.out)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
