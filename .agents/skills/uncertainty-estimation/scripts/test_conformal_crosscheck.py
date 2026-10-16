"""uvx --with mapie --with duckdb --with numpy --with scikit-learn --with pytest pytest test_conformal_crosscheck.py

Against MAPIE (1.5.0): CrossConformalRegressor with method "plus", and ConformalizedQuantileRegressor with
prefit quantile models. MAPIE's CQR corrects the lower and upper ends separately by default (each at its own
1 - alpha / 2 quantile); this script uses one symmetric score, which MAPIE gives with symmetric_correction=True.
"""

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import pytest

from conformal import cqr, fit_cv_plus

mapie_regression = pytest.importorskip("mapie.regression")


def _data(n=57, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 2))
    return X, X @ np.array([1.0, 2.0]) + rng.standard_t(3, size=n), rng.normal(size=(30, 2))


@pytest.mark.parametrize("k", [5, 57])  # 57 folds of one row: the jackknife+
def test_cv_plus_matches_mapie(k):
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import KFold

    X, y, Xt = _data()
    kf = KFold(k)
    folds = np.empty(len(y), int)
    for f, (_, te) in enumerate(kf.split(X)):
        folds[te] = f
    m = mapie_regression.CrossConformalRegressor(LinearRegression(), confidence_level=0.9, method="plus", cv=kf)
    _, iv = m.fit_conformalize(X, y).predict_interval(Xt)
    lo, hi = fit_cv_plus(X, y, Xt, folds, "linear", 0.1)
    np.testing.assert_allclose(lo, iv[:, 0, 0], atol=1e-10)
    np.testing.assert_allclose(hi, iv[:, 1, 0], atol=1e-10)


@pytest.mark.parametrize("alpha", [0.1, 0.2])
def test_cqr_matches_mapie_with_a_symmetric_correction(alpha):
    from sklearn.linear_model import QuantileRegressor

    X, y, Xt = _data(seed=1)
    tr = np.arange(len(y)) < 35
    ests = [QuantileRegressor(quantile=q, alpha=0.0, solver="highs").fit(X[tr], y[tr])
            for q in (alpha / 2, 1 - alpha / 2, 0.5)]  # MAPIE's order: lower, upper, median
    c = mapie_regression.ConformalizedQuantileRegressor(ests, confidence_level=1 - alpha, prefit=True)
    _, iv = c.conformalize(X[~tr], y[~tr]).predict_interval(Xt, symmetric_correction=True)
    lo, hi = cqr(y[~tr], ests[0].predict(X[~tr]), ests[1].predict(X[~tr]), ests[0].predict(Xt), ests[1].predict(Xt),
                 alpha)
    np.testing.assert_allclose(lo, iv[:, 0, 0], atol=1e-10)
    np.testing.assert_allclose(hi, iv[:, 1, 0], atol=1e-10)
