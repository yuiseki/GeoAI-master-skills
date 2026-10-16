"""uvx --from 'duckdb>=1.5.5' --with numpy --with pytest pytest test_gibbs.py"""

import numpy as np
import pytest

from gibbs import (conditional_intensity, fit, gnz_residual, neighbours_within, pair_count, profile_r,
                   simulate)

W = (0.0, 1.0, 0.0, 1.0)


def test_pair_count_and_conditional_intensity_by_hand():
    x, y = np.array([0.0, 0.375, 2.0]), np.array([0.0, 0.5, 2.0])  # first two 0.625 apart (exact in binary)
    assert pair_count(x, y, 0.75) == 1 and pair_count(x, y, 0.625) == 0  # strictly closer than r
    assert neighbours_within(0.125, 0.125, x, y, 0.75).tolist() == [2]
    assert conditional_intensity(0.125, 0.125, x, y, 100.0, 0.5, 0.75)[0] == pytest.approx(25.0)


def test_gamma_one_simulates_a_poisson_count():
    n = [len(simulate(80, 1.0, 0.05, W, seed=s)[0]) for s in range(40)]
    assert np.mean(n) == pytest.approx(80, rel=0.06)
    assert np.var(n) == pytest.approx(80, rel=0.4)


def test_the_count_scales_with_the_window_area():
    # A unit square hides a missing area factor in the acceptance ratio; a 2 x 1.5 window does not.
    n = [len(simulate(40, 1.0, 0.05, (0.0, 2.0, 0.0, 1.5), seed=s)[0]) for s in range(20)]
    assert np.mean(n) == pytest.approx(120, rel=0.08)


def test_gamma_zero_simulates_a_hard_core_and_the_fit_says_so():
    x, y = simulate(100, 0.0, 0.05, W, seed=1)
    assert pair_count(x, y, 0.05) == 0
    f = fit(x, y, W, 0.05)
    assert f["hard_core"] and f["gamma"] == 0.0


def test_the_sampler_satisfies_the_georgii_nguyen_zessin_identity():
    # Under the true parameters, E[n - integral of lambda(u | X)] = 0 over the eroded window: a check of the
    # sampler that does not use the sampler's own acceptance rule.
    res = [gnz_residual(*simulate(150, 0.3, 0.05, W, seed=s), W, 150, 0.3, 0.05) for s in range(40)]
    assert abs(np.mean(res)) < 3 * np.std(res) / np.sqrt(len(res))


def test_maximum_pseudo_likelihood_recovers_the_interaction():
    est = np.array([[f["beta"], f["gamma"]] for f in
                    (fit(*simulate(150, 0.3, 0.05, W, seed=s), W, 0.05) for s in range(10))])
    beta, gamma = est.mean(0)
    assert beta == pytest.approx(150, rel=0.15)
    assert gamma == pytest.approx(0.3, abs=0.1)  # measured mean 0.27, single fits 0.06-0.67


def test_a_poisson_pattern_gets_gamma_near_one():
    g = [fit(*simulate(100, 1.0, 0.05, W, seed=s), W, 0.05)["gamma"] for s in range(8)]
    assert np.mean(g) == pytest.approx(1.0, abs=0.15)


def test_the_profile_over_r_peaks_at_the_true_distance():
    fits = profile_r(*simulate(150, 0.3, 0.05, W, seed=1), W, [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08])
    assert max(fits, key=lambda f: f["log_pl_common"])["r"] == 0.05


def test_clustered_and_trending_patterns_get_gamma_above_one():
    # Strauss cannot describe attraction: a Thomas cluster pattern, and a Poisson pattern whose intensity rises
    # from west to east (no interaction at all), both get gamma > 1. Inhibition in a trending pattern is masked.
    rng = np.random.default_rng(0)
    for s in range(3):
        rng = np.random.default_rng(s)
        k = rng.poisson(6, rng.poisson(15))
        px, py = rng.random(len(k)), rng.random(len(k))
        x = np.repeat(px, k) + rng.normal(0, 0.03, k.sum())
        y = np.repeat(py, k) + rng.normal(0, 0.03, k.sum())
        m = (x > 0) & (x < 1) & (y > 0) & (y < 1)
        assert fit(x[m], y[m], W, 0.05)["gamma"] > 1.3  # measured 1.46-1.72
    g = []
    for s in range(5):
        rng = np.random.default_rng(s)
        n = rng.poisson(300)
        x, y = rng.random(n), rng.random(n)
        keep = rng.random(n) < np.exp(3 * (x - 1))
        g.append(fit(x[keep], y[keep], W, 0.05)["gamma"])
    assert np.mean(g) > 1.15  # measured 1.06-1.49


def test_border_correction_drops_points_near_the_edge():
    x, y = np.array([0.01, 0.5, 0.97]), np.array([0.5, 0.5, 0.5])
    assert fit(x, y, W, 0.05, grid=20)["points_used"] == 1
