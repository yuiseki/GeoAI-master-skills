"""uvx --with numpy --with scipy --with pytest pytest test_hawkes.py"""

import numpy as np
import pytest
from scipy import integrate

from hawkes import background_probability, fit, loglik, simulate

WINDOW = (0.0, 50.0, 0.0, 50.0)  # km


def test_simulation_has_the_expected_number_of_events():
    # Expected count: mu T / (1 - K), less offspring falling after T or outside the window.
    counts = [len(simulate(0.5, 0.5, 1.0, 1.0, 400.0, WINDOW, seed=s)["t"]) for s in range(30)]
    assert np.mean(counts) == pytest.approx(0.5 * 400 / (1 - 0.5), rel=0.08)


def test_log_likelihood_against_numerical_integration_on_a_tiny_example():
    t = np.array([1.0, 1.5, 4.0])
    x = np.array([10.0, 11.0, 30.0])
    y = np.array([10.0, 10.5, 20.0])
    mu, K, beta, sigma, T = 0.4, 0.3, 1.2, 2.0, 6.0
    area = 2500.0

    def lam(tt, xx, yy):
        s = mu / area
        for ti, xi, yi in zip(t, x, y):
            if ti < tt:
                s += K * beta * np.exp(-beta * (tt - ti)) * np.exp(-((xx - xi) ** 2 + (yy - yi) ** 2) / (2 * sigma ** 2)) \
                     / (2 * np.pi * sigma ** 2)
        return s

    point_part = sum(np.log(lam(ti, xi, yi)) for ti, xi, yi in zip(t, x, y))
    # Compensator: the background over the window and time, plus each event's offspring kernel over [t_i, T] (its
    # spatial part integrates to 1 over the plane; the window holds all of it here).
    comp = mu * T + sum(K * integrate.quad(lambda u: beta * np.exp(-beta * u), 0, T - ti)[0] for ti in t)
    assert loglik((mu, K, beta, sigma), t, x, y, T, WINDOW) == pytest.approx(point_part - comp, rel=1e-9)


def test_parameters_are_recovered_from_simulated_events():
    est = []
    for s in range(5):
        d = simulate(0.5, 0.5, 1.0, 1.0, 400.0, WINDOW, seed=100 + s)
        est.append(fit(d["t"], d["x"], d["y"], 400.0, WINDOW)["params"])
    mu, K, beta, sigma = np.mean(est, axis=0)
    assert mu == pytest.approx(0.5, rel=0.15)
    assert K == pytest.approx(0.5, abs=0.08)
    assert beta == pytest.approx(1.0, rel=0.2)
    assert sigma == pytest.approx(1.0, rel=0.15)


def test_a_poisson_pattern_gets_almost_no_triggering():
    d = simulate(1.0, 0.0, 1.0, 1.0, 300.0, WINDOW, seed=7)
    r = fit(d["t"], d["x"], d["y"], 300.0, WINDOW)
    assert r["params"][1] < 0.08
    assert r["lr_test_p"] > 0.01  # triggering not needed


def test_background_probabilities_count_the_background_events():
    d = simulate(0.5, 0.5, 1.0, 1.0, 400.0, WINDOW, seed=11)
    p = background_probability(fit(d["t"], d["x"], d["y"], 400.0, WINDOW)["params"], d["t"], d["x"], d["y"], WINDOW)
    assert p.sum() == pytest.approx(d["is_background"].sum(), rel=0.15)
    assert p[d["is_background"]].mean() > p[~d["is_background"]].mean() + 0.3


def test_a_fixed_hotspot_with_a_uniform_background_looks_like_triggering():
    # No triggering at all, but a fifth of the events sit in a small fixed patch every day. With a uniform
    # background, the model explains the patch by events setting off events.
    rng = np.random.default_rng(3)
    T = 300.0
    n_bg, n_hot = rng.poisson(0.8 * T), rng.poisson(0.2 * T)
    t = np.r_[rng.uniform(0, T, n_bg), rng.uniform(0, T, n_hot)]
    x = np.r_[rng.uniform(0, 50, n_bg), rng.normal(25, 0.5, n_hot)]
    y = np.r_[rng.uniform(0, 50, n_bg), rng.normal(25, 0.5, n_hot)]
    o = np.argsort(t)
    r = fit(t[o], x[o], y[o], T, WINDOW)
    assert r["params"][1] > 0.1 and r["lr_test_p"] < 0.01


def test_events_at_the_same_time_do_not_trigger_each_other():
    # Daily data have many events on the same day; neither can be the other's parent.
    t, x, y = np.array([2.0, 2.0]), np.array([10.0, 10.1]), np.array([10.0, 10.0])
    mu, K, beta, sigma, T = 0.5, 0.5, 1.0, 1.0, 5.0
    expected = 2 * np.log(mu / 2500.0) - mu * T - K * 2 * (1 - np.exp(-beta * 3.0))
    assert loglik((mu, K, beta, sigma), t, x, y, T, WINDOW) == pytest.approx(expected, rel=1e-12)


def test_events_stacked_at_one_point_need_a_floor_on_sigma():
    # Many events share a town's coordinates: without a floor, sigma collapses towards 0.
    d = simulate(0.5, 0.5, 1.0, 1.0, 300.0, WINDOW, seed=21)
    x, y = np.round(d["x"] / 5) * 5, np.round(d["y"] / 5) * 5  # positions snapped to a 5 km grid
    free = fit(d["t"], x, y, 300.0, WINDOW)
    floored = fit(d["t"], x, y, 300.0, WINDOW, min_sigma=2.5)
    assert free["same_place_pairs"] > 0 and free["params"][3] < 0.1
    assert floored["params"][3] >= 2.5
