"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with scikit-learn --with pytest pytest test_st_kriging_crosscheck.py

Against scikit-learn's GaussianProcessRegressor (Cholesky of the kernel matrix, its own code). A product of
Gaussian covariances in space and in time is one Gaussian (RBF) kernel with a length scale per axis:
exp(-h^2 / rs^2) exp(-u^2 / rt^2) = RBF with length scales (rs, rs, rt) / sqrt(2). With the mean known to be 0
(simple kriging), the predictions, their variances and the log-likelihood must agree. The exponential family
has no such kernel in scikit-learn (its Matern kernel takes one distance over all axes: not separable); it is
checked by hand values and the simulated recovery in test_st_kriging.py.
"""

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import pytest

from st_kriging import fit, loglik, predict

gp = pytest.importorskip("sklearn.gaussian_process")
kernels = pytest.importorskip("sklearn.gaussian_process.kernels")


def _data(seed=0, n=120):
    rng = np.random.default_rng(seed)
    P = np.column_stack([rng.random(n), rng.random(n), rng.integers(0, 15, n).astype(float)])
    y = np.sin(4 * P[:, 0]) + np.cos(3 * P[:, 1]) * np.cos(P[:, 2] / 3) + rng.normal(0, 0.3, n)
    return P, y - y.mean()


def _sklearn(params, P, y):
    sill, rs, rt, nugget = params
    k = (kernels.ConstantKernel(sill, "fixed")
         * kernels.RBF(np.array([rs, rs, rt]) / np.sqrt(2), "fixed")
         + kernels.WhiteKernel(nugget, "fixed"))
    return gp.GaussianProcessRegressor(k, optimizer=None, alpha=1e-10 * sill).fit(P, y)


def test_predictions_variances_and_likelihood_match_scikit_learn():
    P, y = _data()
    Q = np.column_stack([np.linspace(0, 1, 7), np.linspace(1, 0, 7), np.arange(7) * 2.5])
    params = np.array([0.8, 0.35, 4.0, 0.09])
    model = {"params": params, "space": "gaussian", "time": "gaussian", "mean": "zero"}
    mu, var, var_obs = predict(model, P, y, Q)
    g = _sklearn(params, P, y)
    gm, gs = g.predict(Q, return_std=True)
    np.testing.assert_allclose(mu, gm, atol=1e-8)
    np.testing.assert_allclose(var_obs, gs ** 2, atol=1e-8)  # scikit-learn's std includes the white noise
    assert loglik(params, P, y, "gaussian", "gaussian", "zero") == pytest.approx(g.log_marginal_likelihood_value_,
                                                                               rel=1e-10)


def test_maximum_likelihood_reaches_scikit_learns_optimum():
    # Points on a line (y = 0): scikit-learn's second spatial length scale then has no effect, and its optimum
    # must equal ours.
    P, y = _data(seed=1, n=150)
    P[:, 1] = 0.0
    ours = fit(P, y, "gaussian", "gaussian", mean="zero")
    k = (kernels.ConstantKernel(0.5, (1e-3, 1e2)) * kernels.RBF([0.3, 0.3, 3.0], (1e-3, 1e3))
         + kernels.WhiteKernel(0.1, (1e-6, 1e1)))
    g = gp.GaussianProcessRegressor(k, n_restarts_optimizer=5, random_state=0).fit(P, y)
    assert ours["loglik"] == pytest.approx(g.log_marginal_likelihood_value_, abs=1e-4)
    sill, rs, rt, nugget = ours["params"]
    ls = g.kernel_.k1.k2.length_scale
    assert rs / np.sqrt(2) == pytest.approx(ls[0], rel=1e-2)
    assert rt / np.sqrt(2) == pytest.approx(ls[2], rel=1e-2)
    assert nugget == pytest.approx(g.kernel_.k2.noise_level, rel=1e-2)
    tied = _sklearn(ours["params"], P, y).log_marginal_likelihood_value_
    assert tied == pytest.approx(ours["loglik"], rel=1e-10)
    for d in (0.9, 1.1):  # and moving any parameter away from it lowers scikit-learn's likelihood
        for i in range(4):
            q = ours["params"].copy()
            q[i] *= d
            assert _sklearn(q, P, y).log_marginal_likelihood_value_ < tied
