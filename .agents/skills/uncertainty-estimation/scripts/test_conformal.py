"""uvx --with duckdb --with numpy --with scikit-learn --with pytest pytest test_conformal.py"""

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import pytest

from conformal import cqr, cv_plus, fit_cv_plus, fit_cqr, rank_quantile


def test_rank_quantile_is_the_finite_sample_order_statistic():
    v = np.array([5.0, 1.0, 3.0, 2.0, 4.0])
    # ceil((1 - 0.2)(5 + 1)) = 5th smallest; ceil(0.9 * 6) = 6 > 5: infinite
    assert rank_quantile(v, 0.2, upper=True) == 5.0
    assert rank_quantile(v, 0.1, upper=True) == np.inf
    # floor(0.2 * 6) = 1st smallest; floor(0.1 * 6) = 0: minus infinity
    assert rank_quantile(v, 0.2, upper=False) == 1.0
    assert rank_quantile(v, 0.1, upper=False) == -np.inf


def test_cv_plus_by_hand():
    # Four training rows in two folds; one test row. Fold 0's model predicts 10 there, fold 1's predicts 12.
    residuals = np.array([1.0, 3.0, 0.5, 2.0])
    fold = np.array([0, 0, 1, 1])
    test_pred = np.array([[10.0], [12.0]])
    # lower values: 10-1, 10-3, 12-0.5, 12-2 = 9, 7, 11.5, 10; upper: 11, 13, 12.5, 14.
    # alpha 0.2, n 4: lower = floor(0.2 * 5) = 1st smallest = 7; upper = ceil(0.8 * 5) = 4th smallest = 14.
    lo, hi = cv_plus(residuals, fold, test_pred, alpha=0.2)
    assert lo.tolist() == [7.0] and hi.tolist() == [14.0]


def test_cv_plus_with_identical_fold_models_is_split_conformal_widened():
    # With every fold model the same, the interval is the prediction plus or minus a residual order statistic.
    rng = np.random.default_rng(0)
    r = np.abs(rng.normal(size=99))
    lo, hi = cv_plus(r, np.arange(99) % 3, np.full((3, 1), 5.0), alpha=0.1)
    k = int(np.ceil(0.9 * 100))
    assert hi[0] - 5.0 == pytest.approx(np.sort(r)[k - 1])
    assert 5.0 - lo[0] == pytest.approx(np.sort(r)[k - 1])  # floor(alpha (n + 1)) = n + 1 - k: symmetric


def test_cqr_by_hand():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    lo_cal = np.array([0.0, 2.5, 2.0, 1.0])
    hi_cal = np.array([2.0, 3.0, 2.5, 5.0])
    # scores max(lo - y, y - hi): -1, 0.5, 0.5, -1. alpha 0.4: ceil(0.6 * 5) = 3rd smallest = 0.5.
    lo, hi = cqr(y, lo_cal, hi_cal, np.array([10.0]), np.array([11.0]), alpha=0.4)
    assert lo.tolist() == [9.5] and hi.tolist() == [11.5]


def _linear_world(rng, n, p=3, noise=None):
    X = rng.normal(size=(n, p))
    s = np.ones(n) if noise is None else noise(X)
    return X, X @ np.arange(1, p + 1) + s * rng.normal(size=n)


def test_cv_plus_covers_new_rows_over_repeated_worlds():
    hits = []
    for s in range(200):
        rng = np.random.default_rng(s)
        X, y = _linear_world(rng, 60)
        Xt, yt = _linear_world(rng, 50)
        lo, hi = fit_cv_plus(X, y, Xt, folds=np.arange(60) % 5, model="linear", alpha=0.1)
        hits.append(np.mean((yt >= lo) & (yt <= hi)))
    assert np.mean(hits) > 0.88  # guaranteed 1 - 2 alpha = 0.8; in practice near 1 - alpha


def test_naive_cross_validation_intervals_undercover_with_an_unstable_model_and_cv_plus_does_not():
    # Ridge with almost no penalty and nearly as many features as rows (Barber et al. 2021). The full-data model's
    # prediction plus or minus the out-of-fold residual quantile undercovers; CV+ uses the fold models themselves.
    from sklearn.linear_model import Ridge

    naive, plus = [], []
    for s in range(60):
        rng = np.random.default_rng(1000 + s)
        n, p = 60, 60  # the full-data model sits at the interpolation threshold; fold models (54 rows) do not
        beta = rng.normal(size=p) / np.sqrt(p)
        X, Xt = rng.normal(size=(n, p)), rng.normal(size=(200, p))
        y, yt = X @ beta + rng.normal(size=n), Xt @ beta + rng.normal(size=200)
        folds = np.arange(n) % 10
        lo, hi = fit_cv_plus(X, y, Xt, folds=folds, model=Ridge(alpha=1e-3), alpha=0.1)
        plus.append(np.mean((yt >= lo) & (yt <= hi)))
        res = np.empty(n)
        for k in range(10):
            m = folds == k
            res[m] = np.abs(y[m] - Ridge(alpha=1e-3).fit(X[~m], y[~m]).predict(X[m]))
        full = Ridge(alpha=1e-3).fit(X, y).predict(Xt)
        q = rank_quantile(res, 0.1, upper=True)
        naive.append(np.mean(np.abs(yt - full) <= q))
    assert np.mean(plus) > 0.9
    assert np.mean(naive) < 0.7  # measured 0.54 (CV+ 0.97); at p 40 or 80 both cover near 0.9


def test_cqr_widths_follow_the_noise_and_the_scaled_score_fixes_an_overfit_quantile_model():
    # Noise 0.3 for half the rows and 3 for the other half. CV+'s near-constant width over-covers the quiet half
    # and under-covers the noisy half. The boosted quantile models follow the noise but overfit (they cover about
    # 75% of new rows on both halves before the correction); CQR's one additive Q then over-covers the quiet half
    # and under-covers the noisy one, while the scaled score corrects both.
    noise = lambda X: np.where(X[:, 0] > 0, 3.0, 0.3)
    cov = {}
    for s in range(10):
        rng = np.random.default_rng(2000 + s)
        X, y = _linear_world(rng, 1500, noise=noise)
        Xt, yt = _linear_world(rng, 1000, noise=noise)
        role = np.where(np.arange(1500) % 3 == 0, "calibration", "train")
        res = {"cv+": fit_cv_plus(X, y, Xt, folds=np.arange(1500) % 5, model="linear", alpha=0.1),
               "cqr": fit_cqr(X, y, role, Xt, model="hgb", alpha=0.1),
               "scaled": fit_cqr(X, y, role, Xt, model="hgb", alpha=0.1, scaled=True)}
        for k, (lo, hi) in res.items():
            for half, m in (("quiet", Xt[:, 0] <= 0), ("noisy", Xt[:, 0] > 0)):
                cov.setdefault((k, half), []).append(np.mean((yt[m] >= lo[m]) & (yt[m] <= hi[m])))
    c = {k: np.mean(v) for k, v in cov.items()}
    assert c["cv+", "quiet"] > 0.97 and c["cv+", "noisy"] < 0.85
    assert c["cqr", "quiet"] > 0.95 and c["cqr", "noisy"] < 0.85
    assert c["scaled", "quiet"] == pytest.approx(0.9, abs=0.03)
    assert c["scaled", "noisy"] == pytest.approx(0.9, abs=0.03)
    for k in ("cv+", "cqr", "scaled"):  # every one keeps the marginal promise
        assert (c[k, "quiet"] + c[k, "noisy"]) / 2 == pytest.approx(0.9, abs=0.025)


def test_coverage_breaks_when_new_rows_are_noisier_than_the_training_rows():
    hits = []
    for s in range(30):
        rng = np.random.default_rng(3000 + s)
        X, y = _linear_world(rng, 200)
        Xt, yt = _linear_world(rng, 200, noise=lambda X: np.full(len(X), 2.0))
        lo, hi = fit_cv_plus(X, y, Xt, folds=np.arange(200) % 5, model="linear", alpha=0.1)
        hits.append(np.mean((yt >= lo) & (yt <= hi)))
    assert np.mean(hits) < 0.65  # 90% promised; a two-sigma-wide noise covers about 59%


def test_scaled_cqr_swaps_crossed_quantiles():
    # The second calibration row's models cross (lower 3, upper 2): swapped to [2, 3], width 1.
    y = np.array([1.0, 2.5, 3.0])
    lo, hi = cqr(y, np.array([0.0, 3.0, 2.0]), np.array([2.0, 2.0, 4.0]), np.array([1.0]), np.array([0.0]),
                 alpha=0.25, scaled=True)
    # scores / widths: -1/2, -0.5/1, -1/2; ceil(0.75 * 4) = 3rd smallest = -0.5; the test row [0, 1] shrinks by half
    assert lo.tolist() == [0.5] and hi.tolist() == [0.5]
