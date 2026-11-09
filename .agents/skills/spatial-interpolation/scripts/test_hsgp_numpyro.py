"""uvx --with numpy --with scipy --with jax==0.12.0.1 --with numpyro==0.22.0 --with pytest pytest test_hsgp_numpyro.py

The basis of hsgp.py against NumPyro's own (numpyro.contrib.hsgp), and the model with inferred parameters on a
surface drawn from a known Matern 5/2 process: the parameters' intervals cover the truth and the 90% predictive
intervals at held-out points hold about 90% of them, with three times the rule's m; with the rule's m, the noise is
overestimated. JAX on the CPU only. About 4 minutes.
"""

import os

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

import numpy as np
import pytest

from hsgp import Box, approx_cov, kernel, rule
from hsgp_numpyro import ell_min, fit, predict


@pytest.mark.parametrize("kind,nu", [("matern52", 2.5), ("matern32", 1.5), ("se", None)])
def test_the_basis_matches_numpyro_contrib_hsgp(kind, nu):
    """Same box, same m: the approximate covariance Phi diag(S) Phi^T (which does not depend on the order of the
    basis functions) agrees with NumPyro's eigenfunctions and spectral densities to 1e-5 (NumPyro computes in float32).
    NumPyro's `alpha` is the variance sigma^2, not sigma: passing sigma gives a covariance sigma times too small."""
    from numpyro.contrib.hsgp.laplacian import eigenfunctions
    from numpyro.contrib.hsgp.spectral_densities import (diag_spectral_density_matern,
                                                         diag_spectral_density_squared_exponential)
    xy = np.random.default_rng(0).uniform(0, 10, (80, 2))
    box, m = Box.around(xy, c=1.6), 9
    ours = approx_cov(xy, xy, box, m, kind, 1.3, 2.0)
    L = [float(x) for x in box.L]
    phi = np.asarray(eigenfunctions(xy - box.center, ell=L, m=[m, m]))
    if nu is None:
        s = diag_spectral_density_squared_exponential(1.3 ** 2, 2.0, ell=L, m=[m, m], dim=2)
    else:
        s = diag_spectral_density_matern(nu, 1.3 ** 2, 2.0, ell=L, m=[m, m], dim=2)
    theirs = (phi * np.asarray(s)) @ phi.T
    assert np.abs(ours - theirs).max() < 1e-5


TRUTH = dict(a=50.0, sigma=4.0, ell=2.0, noise=0.5)


def _surface():
    rng = np.random.default_rng(3)
    xy = rng.uniform(0, 10, (1300, 2))
    K = kernel(xy, xy, "matern52", TRUTH["sigma"], TRUTH["ell"]) + 1e-8 * np.eye(len(xy))
    f = TRUTH["a"] + np.linalg.cholesky(K) @ rng.normal(size=len(xy))
    v = f + TRUTH["noise"] * rng.normal(size=len(xy))
    obs = slice(0, 1000)
    half = Box.around(xy[obs]).half.max()
    c, m = rule("matern52", 1.5, half)      # a guess shorter than the truth
    return xy, f, v, max(c, 2.0), m, half


def test_the_rule_s_m_pushes_the_fine_variation_into_the_noise():
    """With the rule's m (11 per axis), the variation the basis cannot draw is taken as noise: 0.68 for 0.5."""
    xy, f, v, c, m, half = _surface()
    post = fit(xy[:1000], v[:1000], Box.around(xy[:1000], c=c), m, draws=400, warmup=400, chains=2, seed=0)
    assert np.quantile(post["noise"], 0.05) > 0.6


def test_three_times_the_rule_recovers_a_known_surface_and_its_intervals_hold():
    xy, f, v, c, m, half = _surface()
    m = 3 * m
    box = Box.around(xy[:1000], c=c)
    post = fit(xy[:1000], v[:1000], box, m, draws=400, warmup=400, chains=2, seed=0)
    assert post["diverging"] == 0
    for k, t in TRUTH.items():
        lo, hi = np.quantile(post[k], [0.05, 0.95])
        assert lo < t < hi, (k, lo, hi)
    assert np.median(post["ell"]) > ell_min("matern52", c, m, half)
    _, y = predict(post, xy[1000:], box, m)
    lo, hi = np.quantile(y, [0.05, 0.95], axis=0)
    cover = np.mean((v[1000:] > lo) & (v[1000:] < hi))
    assert 0.84 < cover < 0.96, cover
