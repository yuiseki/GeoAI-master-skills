"""uvx --with numpy --with scipy --with pytest pytest test_hsgp.py

The Hilbert-space approximation (HSGP) of a 2-D Gaussian process, in numpy: basis functions on a box, the
approximate covariance against the exact one, the rules for m and c, and the posterior with fixed parameters
against the exact Gaussian process.
"""

import numpy as np
import pytest

from hsgp import (Box, approx_cov, basis, exact_gp, hsgp_posterior, kernel, rule, sqrt_eigenvalues,
                  spectral_density)


def _cloud(n, seed=0, side=10.0):
    return np.random.default_rng(seed).uniform(0, side, size=(n, 2))


def test_the_basis_is_orthonormal_on_the_box():
    """sin functions on [-L, L]^2 scaled by 1/sqrt(L): their inner products over the box are the identity."""
    L = np.array([2.0, 3.0])
    g = np.stack(np.meshgrid(np.linspace(-L[0], L[0], 401), np.linspace(-L[1], L[1], 401)), -1).reshape(-1, 2)
    phi = basis(g, L, m=4)
    gram = phi.T @ phi * (2 * L[0] / 400) * (2 * L[1] / 400)
    assert np.allclose(gram, np.eye(16), atol=0.02)


def test_eigenvalues_grow_with_the_index():
    s = sqrt_eigenvalues(np.array([1.0, 1.0]), m=3)
    assert s.shape == (9,)
    assert s[0] == pytest.approx(np.hypot(np.pi / 2, np.pi / 2))
    assert s.max() == pytest.approx(np.hypot(3 * np.pi / 2, 3 * np.pi / 2))


@pytest.mark.parametrize("kind", ["se", "matern52", "matern32", "matern12"])
def test_spectral_density_integrates_to_the_variance(kind):
    """The 2-D spectral density integrates to k(0) = sigma^2 over the frequency plane (radial integral)."""
    from scipy.integrate import quad
    sigma, ell = 1.3, 0.7
    total = quad(lambda w: spectral_density(np.array([w]), kind, sigma, ell, dim=2)[0] * 2 * np.pi * w, 0, np.inf,
                 limit=500)[0] / (2 * np.pi) ** 2
    assert total == pytest.approx(sigma ** 2, rel=1e-4)


def _edge_distance(xy):
    return np.min(np.minimum(xy - xy.min(0), xy.max(0) - xy), axis=1)


@pytest.mark.parametrize("kind", ["se", "matern52", "matern32"])
def test_the_rule_meets_the_exact_kernel_away_from_the_edges(kind):
    xy = _cloud(400)
    ell = 2.0
    c, m = rule(kind, ell, Box.around(xy).half.max())
    A = approx_cov(xy, xy, Box.around(xy, c=c), m, kind, 1.0, ell)
    K = kernel(xy, xy, kind, 1.0, ell)
    inner = _edge_distance(xy) > ell
    assert np.abs(A - K)[np.ix_(inner, inner)].max() < 0.03


def test_the_minimum_c_of_the_rule_is_too_tight_at_the_edges_in_two_dimensions():
    """Squared exponential, ell = 2, S = 5: the rule's c = 1.28 leaves the variance at 0.46 at an edge point (1 is
    right), and more basis functions do not help. c = 2 brings the whole box within 0.01."""
    xy = _cloud(400)
    ell = 2.0
    c, m = rule("se", ell, Box.around(xy).half.max())
    K = kernel(xy, xy, "se", 1.0, ell)
    tight = approx_cov(xy, xy, Box.around(xy, c=c), 3 * m, "se", 1.0, ell)
    assert np.diag(tight).min() < 0.6
    wide = approx_cov(xy, xy, Box.around(xy, c=2.0), int(np.ceil(m * 2.0 / c)), "se", 1.0, ell)
    assert np.abs(wide - K).max() < 0.01


def test_too_few_basis_functions_break_it():
    xy = _cloud(300)
    ell = 2.0
    c, m = rule("matern52", ell, Box.around(xy, c=None).half.max())
    box = Box.around(xy, c=c)
    K = kernel(xy, xy, "matern52", 1.0, ell)
    assert np.abs(approx_cov(xy, xy, box, max(2, m // 4), "matern52", 1.0, ell) - K).max() > 0.2


def test_a_box_too_tight_breaks_it_near_the_edges():
    """With c close to 1, the basis is pinned to 0 at the boundary, so the variance shrinks at the edge points."""
    xy = _cloud(300)
    ell = 3.0
    box = Box.around(xy, c=1.05)
    A = approx_cov(xy, xy, box, 30, "matern52", 1.0, ell)
    edge = np.min(np.minimum(xy - xy.min(0), xy.max(0) - xy), axis=1) < 0.3
    assert np.diag(A)[edge].min() < 0.7


def test_the_rule_matches_the_paper():
    """Riutort-Mayol et al. (arXiv:2004.11408v2, eq. 18-23): m = a c / (ell / S), c >= max(b ell / S, 1.2)."""
    for kind, a, b in (("se", 1.75, 3.2), ("matern52", 2.65, 4.1), ("matern32", 3.42, 4.5)):
        c, m = rule(kind, ell=1.0, half=5.0)
        assert c == pytest.approx(1.2)
        assert m == int(np.ceil(a * 1.2 / 0.2))
        c, m = rule(kind, ell=2.0, half=5.0)
        assert c == pytest.approx(b * 0.4)
        assert m == int(np.ceil(a * c / 0.4))
    with pytest.raises(ValueError):
        rule("matern12", 1.0, 5.0)


def _posteriors(m_factor, kind="matern52", ell=2.0, noise=0.1, c=2.0):
    rng = np.random.default_rng(1)
    xy, q = _cloud(400, seed=0), _cloud(200, seed=2)
    K = kernel(xy, xy, kind, 1.0, ell) + noise ** 2 * np.eye(400)
    v = np.linalg.cholesky(K) @ rng.normal(size=400) + 5.0
    _, m = rule(kind, ell, Box.around(xy).half.max())
    m = int(np.ceil(m_factor * m))
    return hsgp_posterior(xy, v, q, Box.around(xy, c=c), m, kind, 1.0, ell, noise), exact_gp(xy, v, q, kind, 1.0, ell,
                                                                                               noise)


def test_the_minimum_m_of_the_rule_halves_the_posterior_sd_in_two_dimensions():
    """The rule is for one dimension. With m per axis from it (11, so 121 functions) and little noise (0.1), the
    posterior sd of the latent surface is about 0.6 of the exact one: the approximation is overconfident."""
    (mu_a, sd_a), (mu_e, sd_e) = _posteriors(1)
    assert np.median(sd_a / sd_e) < 0.7


def test_three_times_the_rule_matches_the_exact_gaussian_process():
    (mu_a, sd_a), (mu_e, sd_e) = _posteriors(3)
    assert np.max(np.abs(mu_a - mu_e) / sd_e) < 0.2
    assert np.min(sd_a / sd_e) > 0.9


def test_prediction_points_outside_the_box_are_refused():
    xy = _cloud(50)
    with pytest.raises(ValueError):
        hsgp_posterior(xy, xy[:, 0], np.array([[30.0, 30.0]]), Box.around(xy, c=1.5), 5, "matern52", 1.0, 2.0, 0.1)
