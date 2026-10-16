"""uvx --with numpy --with scipy --with scikit-learn --with pytest pytest test_spde_crosscheck.py

The sparse SPDE kriging against dense Gaussian-process regression with scikit-learn's Matern kernel (nu = 1,
its general-nu form with the Bessel function): scikit-learn writes the Matern correlation with sqrt(2 nu) d /
length_scale, so length_scale = sqrt(2) / kappa. Observations at grid cells, predictions at other cells of the
padded grid's interior. The two differ by the grid's discretisation (h kappa = 0.2 here), not by algebra.
"""

import numpy as np
import pytest

from spde import krige, precision, tau_for

gp = pytest.importorskip("sklearn.gaussian_process")
kernels = pytest.importorskip("sklearn.gaussian_process.kernels")


def test_sparse_spde_kriging_agrees_with_dense_matern_kriging():
    kappa, h, inner, pad = 10.0, 0.02, 51, 30
    n = inner + 2 * pad
    rng = np.random.default_rng(1)
    rows, cols = pad + rng.integers(0, inner, 60), pad + rng.integers(0, inner, 60)
    obs_xy = np.c_[cols, rows] * h
    y = np.sin(obs_xy[:, 0] * 6) + np.cos(obs_xy[:, 1] * 5) + 0.1 * rng.normal(size=60)
    y = y - y.mean()
    noise = 0.05
    out = krige(precision(n, n, h, kappa, tau_for(1.0, kappa)), rows * n + cols, y, noise)
    qr, qc = pad + rng.integers(0, inner, 40), pad + rng.integers(0, inner, 40)
    k = kernels.ConstantKernel(1.0, "fixed") * kernels.Matern(np.sqrt(2) / kappa, "fixed", nu=1.0)
    dense = gp.GaussianProcessRegressor(k, alpha=noise, optimizer=None).fit(obs_xy, y)
    ref, ref_sd = dense.predict(np.c_[qc, qr] * h, return_std=True)
    ours = out["mean"][qr * n + qc]
    assert np.abs(ours - ref).max() < 0.1 * ref_sd.mean()
    assert np.corrcoef(ours, ref)[0, 1] > 0.995


def test_the_likelihood_and_its_maximum_agree_with_dense_matern_regression():
    from spde import fit, loglik, matern_nu1

    kappa, h, inner, pad = 10.0, 0.02, 31, 20
    n = inner + 2 * pad
    rng = np.random.default_rng(2)
    rows, cols = pad + rng.integers(0, inner, 120), pad + rng.integers(0, inner, 120)
    xy = np.c_[cols, rows] * h
    D = np.hypot(*(xy[:, None] - xy[None]).transpose(2, 0, 1))
    y = np.linalg.cholesky(matern_nu1(D, 1.0, kappa) + 0.05 * np.eye(120)) @ rng.normal(size=120)
    cells = rows * n + cols
    k = kernels.ConstantKernel(1.0, "fixed") * kernels.Matern(np.sqrt(2) / kappa, "fixed", nu=1.0)
    dense = gp.GaussianProcessRegressor(k, alpha=0.05, optimizer=None).fit(xy, y)
    assert loglik(n, n, h, cells, y, kappa, 1.0, 0.05) == pytest.approx(dense.log_marginal_likelihood_value_, abs=1.5)
    ours = fit(n, n, h, cells, y)
    k = (kernels.ConstantKernel(1.0, (1e-3, 1e2)) * kernels.Matern(0.14, (1e-3, 10), nu=1.0)
         + kernels.WhiteKernel(0.1, (1e-5, 10)))
    g = gp.GaussianProcessRegressor(k, n_restarts_optimizer=4, random_state=0).fit(xy, y).kernel_
    assert ours["kappa"] == pytest.approx(np.sqrt(2) / g.k1.k2.length_scale, rel=0.1)
    assert ours["sigma2"] == pytest.approx(g.k1.k1.constant_value, rel=0.1)
    assert ours["noise_var"] == pytest.approx(g.k2.noise_level, rel=0.15)
