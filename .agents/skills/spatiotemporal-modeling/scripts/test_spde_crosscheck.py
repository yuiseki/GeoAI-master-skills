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
