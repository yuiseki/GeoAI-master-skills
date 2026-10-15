"""uvx --with numpy --with pytest pytest test_bayes_conjugate.py

Closed forms checked by hand; the simulations check a property of seeded draws.
"""

import math

import numpy as np
import pytest

from bayes_conjugate import (beta_binomial, beta_binomial_predictive, beta_cdf, beta_interval, coverage_normal,
                             gamma_poisson, gamma_poisson_predictive, linear_gaussian, normal_normal,
                             normal_predictive, ppc, simulate_prior_predictive)


def test_seven_in_a_hundred_with_a_uniform_and_an_informative_prior():
    flat = beta_binomial(7, 100, 1, 1)
    assert (flat["a"], flat["b"]) == (8, 94) and flat["mean"] == pytest.approx(8 / 102)
    informed = beta_binomial(7, 100, 2, 18)  # prior mean 0.1, worth 20 trials
    assert (informed["a"], informed["b"]) == (9, 111) and informed["mean"] == pytest.approx(9 / 120)


def test_the_beta_cdf_and_interval_against_closed_forms():
    assert beta_cdf(0.3, 1, 1) == pytest.approx(0.3)
    assert beta_cdf(0.3, 2, 1) == pytest.approx(0.09)  # x^2
    assert beta_cdf(0.3, 2, 2) == pytest.approx(3 * 0.09 - 2 * 0.027)  # 3x^2 - 2x^3
    lo, hi = beta_interval(2, 1)
    assert (lo, hi) == pytest.approx((math.sqrt(0.025), math.sqrt(0.975)), abs=1e-9)


def test_posterior_predictive_of_two_future_trials_by_hand():
    # one success in two, uniform prior -> Beta(2, 2); B(2, 2) = 1/6, B(2, 4) = 1/20, B(3, 3) = 1/30
    post = beta_binomial(1, 2)
    assert beta_binomial_predictive(2, post["a"], post["b"]) == pytest.approx([0.3, 0.4, 0.3])
    # a known p = 0.5 would give 0.25, 0.5, 0.25: the parameter's uncertainty widens the prediction
    assert sum(beta_binomial_predictive(5, 3, 9)) == pytest.approx(1)


def test_an_improper_posterior_stops():
    with pytest.raises(ValueError, match="improper"):
        beta_binomial(0, 10, 0, 0)  # Beta(0, 10)
    assert beta_binomial(1, 10, 0, 0)["mean"] == pytest.approx(0.1)  # proper once both counts are positive


def test_normal_posterior_is_the_precision_weighted_average():
    # prior N(0, 4), one observation 3 with variance 1: precision 1/4 + 1 = 5/4
    p = normal_normal(0, 4, 3, 1, 1)
    assert p["var"] == pytest.approx(0.8) and p["mean"] == pytest.approx(2.4)
    assert p["weight_on_data"] == pytest.approx(0.8)  # = v0 / (v0 + s2 / n) = 4 / 5, the pooling weight
    pred = normal_predictive(p["mean"], p["var"], 1)
    assert pred["var"] == pytest.approx(1.8)  # parameter 0.8 + a single observation 1


def test_the_data_weight_is_the_multilevel_pooling_weight_for_any_group_size():
    for n in (1, 3, 30):
        assert normal_normal(0, 2.0, 1, 5.0, n)["weight_on_data"] == pytest.approx(2.0 / (2.0 + 5.0 / n))


def test_a_strong_wrong_prior_fades_but_slowly():
    wrong = (500, 500)  # mean 0.5, worth 1,000 trials; the data say 0.07
    assert beta_binomial(7, 100, *wrong)["mean"] == pytest.approx(507 / 1100)  # 0.461
    assert beta_binomial(700, 10_000, *wrong)["mean"] == pytest.approx(1200 / 11_000)  # 0.109
    assert beta_binomial(7, 100, 1, 1)["mean"] - beta_binomial(7, 100, 2, 18)["mean"] == pytest.approx(
        8 / 102 - 9 / 120)


def test_a_sum_identifies_the_sum_but_never_its_parts():
    # y depends on a + b only; priors N(0, 1) each. posterior var(a) = (1 + n) / (1 + 2n) -> 1/2
    for n in (10, 100_000):
        X = np.ones((n, 2))
        post = linear_gaussian(X, np.full(n, 3.0), [0, 0], np.eye(2), 1.0)
        assert post["cov"][0, 0] == pytest.approx((1 + n) / (1 + 2 * n))
        assert post["cov"][0, 0] + post["cov"][1, 1] + 2 * post["cov"][0, 1] == pytest.approx(2 / (1 + 2 * n))


def test_gamma_poisson_posterior_and_predictive_by_hand():
    p = gamma_poisson([3, 5], [1, 1], 2, 1)
    assert (p["a"], p["b"]) == (10, 3)
    # exposure is person-years (or area), not the number of rows: 2 + 0.5 added to the rate parameter
    assert gamma_poisson([3, 5], [2, 0.5], 2, 1)["b"] == pytest.approx(3.5)
    pred = gamma_poisson_predictive(10, 3, 2)
    assert pred["mean"] == pytest.approx(20 / 3)
    assert pred["var"] == pytest.approx(20 / 3 + 4 * 10 / 9)


def test_a_prior_that_looks_vague_can_predict_absurd_counts():
    rng = np.random.default_rng(0)
    # accidents per person-year in a town of 100,000: Gamma(1, 1) means one accident per person a year
    flat = simulate_prior_predictive(1, 1, 100_000, rng)
    assert np.median(flat) > 50_000
    # Gamma(0.001, 0.001), often called vague: mostly zero accidents, now and then millions
    vague = simulate_prior_predictive(0.001, 0.001, 100_000, rng)
    assert np.mean(vague == 0) > 0.9 and vague.max() > 1_000_000
    # a prior centred on 1 in 10,000 a year, a factor of about 3 either way: 10 accidents, rarely 100
    sensible = simulate_prior_predictive(4, 40_000, 100_000, rng)
    assert 5 < np.median(sensible) < 15 and np.quantile(sensible, 0.999) < 100


def _poisson_replicate(y):
    post = gamma_poisson(y, np.ones(len(y)), 1, 1)
    return lambda rng: rng.poisson(rng.gamma(post["a"], 1 / post["b"]), len(y))


def test_a_poisson_model_cannot_reproduce_the_zeros_of_overdispersed_counts():
    rng = np.random.default_rng(1)
    over = rng.negative_binomial(0.5, 0.5 / 2.5, 200)  # mean 2, variance 10
    r = ppc(over, _poisson_replicate(over), lambda y: np.sum(y == 0), rng)
    assert r["p"] < 0.01  # more zeros than any replicate
    fine = rng.poisson(2, 200)
    r = ppc(fine, _poisson_replicate(fine), lambda y: np.sum(y == 0), rng)
    assert 0.05 < r["p"] < 0.95


def test_a_strong_wrong_prior_breaks_coverage_at_small_n_and_less_at_large_n():
    rng = np.random.default_rng(2)
    weak = coverage_normal(0, 0, 100, 1, 5, rng)
    small = coverage_normal(0, 3, 0.01, 1, 5, rng)
    assert weak["coverage"] == pytest.approx(0.95, abs=0.02)
    assert small["coverage"] < 0.01 and small["bias"] > 2.5
    # the prior is worth 100 observations: the bias is 300 / (100 + n), the posterior sd 1 / sqrt(100 + n).
    # At n = 5,000 the bias is small (0.059) but still 4.2 posterior sds: the interval almost never covers.
    mid = coverage_normal(0, 3, 0.01, 1, 5000, rng)
    assert mid["bias"] == pytest.approx(300 / 5100, abs=0.002) and mid["coverage"] < 0.05
    # only when 300 / sqrt(100 + n) is well below 1 does coverage come back (n = 10^6: 0.3 sds)
    assert coverage_normal(0, 3, 0.01, 1, 1_000_000, rng)["coverage"] > 0.9


def test_intervals_match_values_recorded_from_scipy():
    # scipy.stats.beta.ppf([0.025, 0.975], a, b), recorded 2026-10-15; scipy is not needed to run this
    assert beta_interval(8, 94) == pytest.approx((0.03481691, 0.13759588), abs=1e-8)
    assert beta_interval(0.5, 30.5) == pytest.approx((1.62318612e-05, 7.96781738e-02), rel=1e-6)
