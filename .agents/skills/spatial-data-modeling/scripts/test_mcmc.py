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
