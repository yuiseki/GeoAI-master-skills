"""uvx --with numpy --with scipy --with pytest pytest test_mcmc.py"""

import numpy as np
import pytest
from scipy import stats

from mcmc import ess_bulk, poisson_random_intercepts, rhat, sample


def test_independent_draws_have_rhat_near_one_and_ess_near_the_count():
    x = np.random.default_rng(0).normal(size=(4, 1000))
    assert rhat(x) == pytest.approx(1.0, abs=0.01)
    assert 3000 < ess_bulk(x) < 5000


def test_chains_in_different_places_have_a_large_rhat():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(4, 1000)) + np.array([0, 0, 3, 3])[:, None]
    assert rhat(x) > 1.5


def test_split_rhat_sees_a_chain_that_drifts_within_itself():
    # Every chain wanders from -1 to +1 over its run: the chains agree with each other, but not with themselves.
    rng = np.random.default_rng(10)
    x = rng.normal(scale=0.3, size=(4, 1000)) + np.linspace(-1, 1, 1000)
    assert rhat(x) > 1.2


def test_a_sticky_chain_has_a_small_ess():
    rng = np.random.default_rng(2)
    x = np.zeros((4, 1000))
    for c in range(4):
        for t in range(1, 1000):
            x[c, t] = 0.98 * x[c, t - 1] + rng.normal()
    assert ess_bulk(x) < 200


def test_normal_mean_matches_the_conjugate_posterior():
    # y ~ N(mu, 2^2), mu ~ N(0, 5^2): the posterior is normal with known mean and sd.
    rng = np.random.default_rng(3)
    y = rng.normal(1.5, 2.0, size=30)
    prec = 1 / 25 + len(y) / 4
    post_mean, post_sd = (y.sum() / 4) / prec, prec ** -0.5
    logp = lambda th: stats.norm.logpdf(y, th[0], 2.0).sum() + stats.norm.logpdf(th[0], 0, 5)
    r = sample(logp, np.zeros(1), draws=2000, warmup=1000, chains=4, seed=0)
    d = r["draws"][:, :, 0]
    mc_se = d.std() / np.sqrt(ess_bulk(d))
    assert rhat(d) < 1.01
    assert abs(d.mean() - post_mean) < 4 * mc_se
    assert d.std() == pytest.approx(post_sd, rel=0.08)


def test_poisson_rate_matches_the_gamma_posterior():
    rng = np.random.default_rng(4)
    y = rng.poisson(3.0, size=40)
    a, b = 2.0, 1.0  # gamma prior on the rate; the sampler works on its log
    logp = lambda th: (stats.poisson.logpmf(y, np.exp(th[0])).sum()
                       + stats.gamma.logpdf(np.exp(th[0]), a, scale=1 / b) + th[0])  # + log Jacobian
    r = sample(logp, np.zeros(1), draws=2000, warmup=1000, chains=4, seed=1)
    rate = np.exp(r["draws"][:, :, 0])
    post = stats.gamma(a + y.sum(), scale=1 / (b + len(y)))
    assert rate.mean() == pytest.approx(post.mean(), rel=0.02)
    assert np.quantile(rate, 0.9) == pytest.approx(post.ppf(0.9), rel=0.03)


def test_dropping_the_jacobian_samples_another_posterior():
    # Without + log rate, the sampler targets Gamma(a + sum y - 1, b + n): the mean moves by 1 / (b + n).
    y = np.array([2, 4, 3, 1, 5])
    logp = lambda th: stats.poisson.logpmf(y, np.exp(th[0])).sum() + stats.gamma.logpdf(np.exp(th[0]), 2.0, scale=1.0)
    rate = np.exp(sample(logp, np.zeros(1), draws=4000, warmup=1000, chains=4, seed=1)["draws"][:, :, 0])
    right, wrong = (2.0 + y.sum()) / 6, (2.0 + y.sum() - 1) / 6
    assert rate.mean() == pytest.approx(wrong, abs=0.06)
    assert abs(rate.mean() - right) > 0.1


def test_simulation_based_calibration_of_the_random_intercept_model():
    # Draw the parameters from the prior, simulate counts, fit, and rank the true value among the draws:
    # ranks are uniform when the sampler and the model agree.
    ranks = []
    for rep in range(60):
        rng = np.random.default_rng(1000 + rep)
        alpha = rng.normal(0, 1)
        sigma = abs(rng.normal(0, 1))
        u = rng.normal(0, sigma, 8)
        area = np.repeat(np.arange(8), 5)
        y = rng.poisson(np.exp(alpha + u[area]))
        r = poisson_random_intercepts(y, area, draws=400, warmup=600, chains=2, seed=rep)
        a, s_ = r["alpha"].ravel()[::8], r["sigma"].ravel()[::8]
        ranks.append(((a < alpha).sum() / len(a), (s_ < sigma).sum() / len(s_)))
    ranks = np.array(ranks)
    assert stats.kstest(ranks[:, 0], "uniform").pvalue > 0.01
    assert stats.kstest(ranks[:, 1], "uniform").pvalue > 0.01  # sigma: sensitive to its log-Jacobian


# Hamiltonian Monte Carlo and the BYM2 model

def test_hmc_recovers_a_correlated_gaussian():
    from mcmc import hmc

    mean = np.array([1.0, -2.0, 0.5])
    cov = np.array([[1.0, 0.9, 0.0], [0.9, 1.0, 0.0], [0.0, 0.0, 0.01]])  # strong correlation, and a narrow axis
    P = np.linalg.inv(cov)

    def f(x):
        d = x - mean
        return float(-0.5 * d @ P @ d), -P @ d

    r = hmc(f, np.zeros(3), draws=1500, warmup=1000, chains=4, seed=1)
    d = r["draws"].reshape(-1, 3)
    se = np.sqrt(np.diag(cov) / 1000)  # a conservative effective size
    assert np.all(np.abs(d.mean(0) - mean) < 4 * se)
    np.testing.assert_allclose(np.cov(d.T), cov, atol=0.1)
    assert all(rhat(r["draws"][:, :, j]) < 1.01 for j in range(3))
    assert r["divergent"].sum() == 0


def _ring(n):
    return [np.array([(i - 1) % n, (i + 1) % n]) for i in range(n)]


def test_bym2_gradient_matches_finite_differences_with_an_island():
    from mcmc import bym2_logp_grad

    nb = _ring(6) + [np.array([], int)]  # six areas in a ring and one island
    rng = np.random.default_rng(2)
    E = rng.uniform(2, 8, 7)
    y = rng.poisson(E)
    f, info = bym2_logp_grad(nb, y, E)
    assert info["components"] == 2 and info["alone"] == 1
    x = rng.normal(scale=0.5, size=3 + 14)
    lp, g = f(x)
    num = np.array([(f(x + h)[0] - f(x - h)[0]) / 2e-6 for h in np.eye(len(x)) * 1e-6])
    np.testing.assert_allclose(g, num, rtol=1e-5, atol=1e-5)


def test_bym2_scaling_of_a_ring_by_hand():
    from mcmc import bym2_scaling, neighbour_components

    # The ring's ICAR precision is circulant; its generalised inverse's diagonal is (n^2 - 1) / (12 n) for a ring of
    # n (the same for every unit), so the geometric mean is that value.
    nb = _ring(8)
    s = bym2_scaling(nb, neighbour_components(nb))
    np.testing.assert_allclose(s, (64 - 1) / (12 * 8), rtol=1e-10)


def test_bym2_recovers_a_spatial_share_from_simulated_counts():
    from mcmc import bym2_scaling, neighbour_components, poisson_bym2

    # A 6 x 6 grid (rook), structured effect only (rho 1), sigma 0.8: the posterior puts rho high.
    side = 6
    nb = []
    for i in range(side * side):
        r, c = divmod(i, side)
        nb.append(np.array([j for j in (i - side, i + side, i - 1 if c else -1, i + 1 if c < side - 1 else -1)
                            if 0 <= j < side * side]))
    rng = np.random.default_rng(3)
    Q = np.zeros((36, 36))
    for i, v in enumerate(nb):
        Q[i, v] = -1
        Q[i, i] = len(v)
    s = bym2_scaling(nb, neighbour_components(nb))
    w, V = np.linalg.eigh(Q)
    phi = V[:, 1:] @ (rng.normal(size=35) / np.sqrt(w[1:]))
    b = 0.8 * phi / np.sqrt(s)
    E = np.full(36, 30.0)
    y = rng.poisson(E * np.exp(b))
    # rho's posterior sits near its upper boundary (median 0.97), where it mixes slowly: with 800 warm-up draws
    # sigma's R-hat was 1.04, with 2,000 it was 1.005.
    r = poisson_bym2(y, E, nb, draws=800, warmup=2000, chains=4, seed=4)
    assert np.median(r["rho"]) > 0.5
    assert np.corrcoef(r["b"].reshape(-1, 36).mean(0), b)[0, 1] > 0.8
    assert rhat(r["sigma"]) < 1.02 and rhat(r["alpha"]) < 1.02
    assert r["divergent"].sum() == 0


def test_bym2_scaling_survives_a_larger_irregular_graph():
    # A 53-unit graph made the default pseudo-inverse return negative variances (its zero eigenvalue, -4e-16,
    # was not cut). The exact generalised inverse of a connected Laplacian has a positive diagonal.
    from mcmc import bym2_scaling, neighbour_components

    rng = np.random.default_rng(5)
    pts = rng.random((53, 2))
    d = np.hypot(*(pts[:, None] - pts[None]).transpose(2, 0, 1))
    nb = [np.argsort(d[i])[1:4] for i in range(53)]
    nb = [np.array(sorted(set(nb[i].tolist()) | {j for j in range(53) if i in nb[j]})) for i in range(53)]
    lab = neighbour_components(nb)
    s = bym2_scaling(nb, lab)
    assert np.all(np.isfinite(s)) and np.all(s > 0)


def test_bym2_without_information_in_the_data_returns_the_priors():
    # Expected counts near 0 and no cases: the likelihood is flat, so the draws must follow the priors:
    # sigma half-normal(1) (median 0.674), rho Beta(0.5, 0.5) (median 0.5). A missing log-Jacobian of either
    # transform moves these medians, though it can pass a comparison on informative data.
    from mcmc import poisson_bym2

    nb = _ring(6)
    r = poisson_bym2(np.zeros(6), np.full(6, 1e-9), nb, draws=1500, warmup=1500, chains=4, seed=6)
    assert np.median(r["sigma"]) == pytest.approx(stats.halfnorm.median(), abs=0.06)
    assert np.median(r["rho"]) == pytest.approx(0.5, abs=0.08)
    assert np.mean(r["sigma"] < 0.2) == pytest.approx(stats.halfnorm.cdf(0.2), abs=0.04)
