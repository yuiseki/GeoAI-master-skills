"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pytest pytest test_bayes_conjugate_crosscheck.py

bayes_conjugate's closed forms against scipy.stats over a grid of parameters: Beta quantiles (the credible
interval), the Beta-binomial distribution (the posterior predictive of a rate) and the negative binomial (the
Gamma-Poisson predictive of a count). Set GEOAI_REALDATA=1 to also update on a real share: evacuation sites in
Tokyo designated for tsunami.
"""

import os

import numpy as np
import pytest
from scipy import stats

from bayes_conjugate import (beta_binomial, beta_binomial_predictive, beta_interval, gamma_poisson,
                             gamma_poisson_predictive, normal_normal)

GRID = [(a, b) for a in (0.3, 0.5, 1, 2, 8, 50, 500) for b in (0.4, 1, 3, 30, 94, 1000)]


@pytest.mark.parametrize("a,b", GRID)
def test_beta_intervals_match_scipy(a, b):
    for level in (0.5, 0.9, 0.95, 0.99):
        lo, hi = beta_interval(a, b, level)
        tail = (1 - level) / 2
        assert (lo, hi) == pytest.approx(tuple(stats.beta.ppf([tail, 1 - tail], a, b)), rel=1e-7, abs=1e-12)


@pytest.mark.parametrize("a,b", GRID)
def test_beta_binomial_predictive_matches_scipy(a, b):
    for m in (1, 5, 40):
        assert beta_binomial_predictive(m, a, b) == pytest.approx(stats.betabinom.pmf(range(m + 1), m, a, b), rel=1e-9)


def test_gamma_poisson_predictive_matches_the_negative_binomial():
    for a, b, e in ((2, 1, 3), (10, 3, 2), (4, 40_000, 100_000), (0.5, 0.1, 7)):
        # count ~ NB(n = a, p = b / (b + e)) in scipy's parameterisation
        nb = stats.nbinom(a, b / (b + e))
        pred = gamma_poisson_predictive(a, b, e)
        assert pred["mean"] == pytest.approx(nb.mean(), rel=1e-12)
        assert pred["var"] == pytest.approx(nb.var(), rel=1e-12)


def test_normal_posterior_matches_scipy_by_brute_force():
    # posterior on a fine grid: prior density x likelihood of the mean of n observations, normalised
    m0, v0, ybar, s2, n = 1.0, 4.0, 3.0, 2.0, 5
    grid = np.linspace(-10, 15, 200_001)
    post = stats.norm.pdf(grid, m0, np.sqrt(v0)) * stats.norm.pdf(ybar, grid, np.sqrt(s2 / n))
    post /= np.trapezoid(post, grid)
    mean = np.trapezoid(grid * post, grid)
    var = np.trapezoid((grid - mean) ** 2 * post, grid)
    p = normal_normal(m0, v0, ybar, s2, n)
    assert (p["mean"], p["var"]) == pytest.approx((mean, var), rel=1e-8)


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_share_of_tokyo_sites_designated_for_tsunami():
    duckdb = pytest.importorskip("duckdb")
    k, n = duckdb.sql("""select count(*) filter (where tsunami), count(*)
                         from 'hf://datasets/yuiseki/gsi-evacuation-sites-jp/parquet/sites.parquet'
                         where municipality like '東京都%'""").fetchone()
    post = beta_binomial(k, n, 1, 1)
    assert post["mean"] == pytest.approx(stats.beta(1 + k, 1 + n - k).mean(), rel=1e-12)
    assert beta_interval(post["a"], post["b"]) == pytest.approx(tuple(stats.beta.ppf([0.025, 0.975], post["a"], post["b"])), rel=1e-7)
    counts = duckdb.sql("""select count(*) from 'hf://datasets/yuiseki/gsi-evacuation-sites-jp/parquet/sites.parquet'
                           where municipality like '東京都%' group by municipality""").fetchall()
    g = gamma_poisson([c[0] for c in counts], np.ones(len(counts)), 1, 0.01)
    assert g["mean"] == pytest.approx(stats.gamma(g["a"], scale=1 / g["b"]).mean(), rel=1e-12)
