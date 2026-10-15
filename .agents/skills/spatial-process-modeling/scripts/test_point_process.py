"""uvx --with numpy --with pytest pytest test_point_process.py

Small patterns with known maximum likelihood are worked out by hand; the simulated worlds check a property of
seeded draws.
"""

import math

import numpy as np
import pytest

from point_process import (bump_field, cell_means, conditional_fit, expected_count, fit_grid_poisson, fit_poisson_process,
                           grid_counts, intensity_upper, mean_nn_distance, monte_carlo_p, pearson_dispersion,
                           quadrature, simulate_poisson, simulate_thomas)

UNIT = (0.0, 1.0, 0.0, 1.0)


def upper(intensity, window=UNIT):
    return intensity_upper(intensity, window)


def left(xy):
    return (np.asarray(xy)[:, 0] < 0.5).astype(float)[:, None]


def two_halves(n_left, n_right):
    rng = np.random.default_rng(0)
    return np.r_[np.c_[rng.uniform(0, 0.5, n_left), rng.random(n_left)],
                 np.c_[rng.uniform(0.5, 1, n_right), rng.random(n_right)]]


def test_a_homogeneous_fit_is_the_count_over_the_area():
    pts = two_halves(30, 10)
    q, w = quadrature(UNIT, 20)
    r = fit_poisson_process(np.empty((40, 0)), np.empty((len(q), 0)), w)
    assert math.exp(r["beta"][0]) == pytest.approx(40)
    assert r["se"][0] == pytest.approx(1 / math.sqrt(40))


def test_a_two_region_intensity_is_each_count_over_its_area():
    # 30 points in the left half (area 0.5) and 10 in the right: 60 and 20 per unit area
    pts = two_halves(30, 10)
    q, w = quadrature(UNIT, 20)  # cell edges fall on x = 0.5
    r = fit_poisson_process(left(pts), left(q), w)
    assert math.exp(r["beta"][0]) == pytest.approx(20)
    assert r["beta"][1] == pytest.approx(math.log(3))


def test_counting_on_cells_aligned_with_the_regions_gives_the_same_answer():
    pts = two_halves(30, 10)
    g = grid_counts(pts, UNIT, cell=0.25)
    r = fit_grid_poisson(g["counts"], left(g["centres"]), g["area"])
    assert r["beta"] == pytest.approx([math.log(20), math.log(3)])


def test_expected_count_is_the_integral_of_the_intensity():
    # log lambda = a + b x on the unit square: integral e^a (e^b - 1) / b
    a, b = math.log(50), 1.2
    got = expected_count(lambda xy: np.exp(a + b * xy[:, 0]), UNIT, n=200)
    assert got == pytest.approx(math.exp(a) * (math.exp(b) - 1) / b, rel=1e-4)


def test_homogeneous_counts_are_poisson_and_locations_uniform():
    rng = np.random.default_rng(1)
    n = [len(simulate_poisson(lambda xy: np.full(len(xy), 100.0), UNIT, 100.0, rng)) for _ in range(2000)]
    assert np.mean(n) == pytest.approx(100, abs=1) and np.var(n) == pytest.approx(100, rel=0.1)
    pts = simulate_poisson(lambda xy: np.full(len(xy), 5000.0), UNIT, 5000.0, rng)
    g = grid_counts(pts, UNIT, cell=0.25)
    assert pearson_dispersion(g["counts"], np.full(16, len(pts) / 16), 1) == pytest.approx(1, abs=0.5)


def _inhomogeneous(seed):
    rng = np.random.default_rng(seed)
    pts = simulate_poisson(lambda xy: np.exp(5 + 2 * xy[:, 0]), UNIT, math.exp(7), rng)
    return rng, pts


def test_an_inhomogeneous_fit_recovers_beta_and_the_homogeneous_one_cannot_explain_the_pattern():
    rng, pts = _inhomogeneous(2)
    q, w = quadrature(UNIT, 100)
    full = fit_poisson_process(pts[:, :1], q[:, :1], w)
    flat = fit_poisson_process(np.empty((len(pts), 0)), np.empty((len(q), 0)), w)
    assert full["beta"] == pytest.approx([5, 2], abs=3 * max(full["se"]))
    assert 2 * (full["loglik"] - flat["loglik"]) > 10.83  # chi-square, 1 df, p < 0.001
    g = grid_counts(pts, UNIT, cell=0.1)
    e_flat = g["area"] * len(pts)
    e_full = g["area"] * np.exp(full["beta"][0] + full["beta"][1] * g["centres"][:, 0])
    assert pearson_dispersion(g["counts"], e_flat, 1) > 2
    assert pearson_dispersion(g["counts"], e_full, 2) == pytest.approx(1, abs=0.4)


def test_conditioning_on_the_count_gives_the_same_slope_without_the_intercept():
    _, pts = _inhomogeneous(3)
    q, w = quadrature(UNIT, 100)
    full = fit_poisson_process(pts[:, :1], q[:, :1], w)
    cond = conditional_fit(pts[:, :1], q[:, :1], w)
    assert cond["beta"][0] == pytest.approx(full["beta"][1], abs=1e-8)


def test_a_coarse_grid_and_its_origin_move_the_estimate_of_a_fine_scale_covariate():
    # the covariate varies over about 0.05; cells of 0.02 resolve it, cells of 0.25 do not. Five worlds.
    exact, fine, coarse, shifted, averaged = [], [], [], [], []
    for seed in range(5):
        rng = np.random.default_rng(seed)
        x = bump_field(UNIT, rng, n_bumps=40, width=0.05)
        lam = lambda xy: np.exp(5 + 1.0 * x(xy))
        pts = simulate_poisson(lam, UNIT, upper(lam), rng)
        q, w = quadrature(UNIT, 200)
        exact.append(fit_poisson_process(x(pts)[:, None], x(q)[:, None], w)["beta"][1])
        g = grid_counts(pts, UNIT, cell=0.02)
        r = fit_grid_poisson(g["counts"], x(g["centres"])[:, None], g["area"])
        assert r["zeros"] > 0.8  # mostly empty cells are not a problem for Poisson
        fine.append(r["beta"][1])
        for o, store in ((0.0, coarse), (0.125, shifted)):
            g = grid_counts(pts, UNIT, cell=0.25, origin=o)
            store.append(fit_grid_poisson(g["counts"], x(g["centres"])[:, None], g["area"])["beta"][1])
        g = grid_counts(pts, UNIT, cell=0.25)
        averaged.append(fit_grid_poisson(g["counts"], cell_means(x, g, UNIT)[:, None], g["area"])["beta"][1])
    assert np.mean(exact) == pytest.approx(1.0, abs=0.1)
    assert np.mean(np.abs(np.array(fine) - exact)) < 0.08
    assert np.mean(coarse) < 0.7 and np.mean(shifted) < 0.7  # the centre value misses the variation in a cell
    assert np.mean(np.abs(np.array(coarse) - shifted)) > 0.1  # and which variation depends on the origin
    assert np.mean(averaged) > 0.9


def test_cells_cut_by_the_window_need_their_true_area():
    rng = np.random.default_rng(5)
    win = (0.0, 1.0, 0.0, 0.9)  # the top row of 0.25 cells is only 0.15 high
    pts = simulate_poisson(lambda xy: np.full(len(xy), 200.0), win, 200.0, rng)
    g = grid_counts(pts, win, cell=0.25)
    top = (g["centres"][:, 1] > 0.75).astype(float)[:, None]
    right = fit_grid_poisson(g["counts"], top, g["area"])
    wrong = fit_grid_poisson(g["counts"], top, np.full(len(g["area"]), 0.0625))
    assert abs(right["beta"][1]) < 2 * right["se"][1]
    assert wrong["beta"][1] < -0.4  # the cut cells look emptier than they are: 0.15 / 0.25 -> log 0.6


def _clustered_worlds(seed):
    rng = np.random.default_rng(seed)
    x = lambda xy: xy[:, 0]
    z = bump_field(UNIT, rng, n_bumps=15, width=0.06)  # unobserved environment
    lam = lambda xy: np.exp(4 + x(xy) + 1.5 * z(xy))
    cox = simulate_poisson(lam, UNIT, upper(lam), rng)
    thomas = simulate_thomas(kappa=25, mu=12, sigma=0.03, window=UNIT, rng=rng)
    return rng, x, cox, thomas


def test_a_covariate_model_leaves_clustering_from_an_unobserved_environment_and_from_contagion_alike():
    rng, x, cox, thomas = _clustered_worlds(6)
    q, w = quadrature(UNIT, 100)
    out = {}
    for name, pts in (("cox", cox), ("thomas", thomas)):
        fit = fit_poisson_process(x(pts)[:, None], x(q)[:, None], w)
        lam = lambda xy, b=fit["beta"]: np.exp(b[0] + b[1] * x(xy))
        g = grid_counts(pts, UNIT, cell=0.1)
        out[name] = pearson_dispersion(g["counts"], g["area"] * lam(g["centres"]), 2)
        sims = [mean_nn_distance(simulate_poisson(lam, UNIT, upper(lam), rng)) for _ in range(99)]
        assert monte_carlo_p(mean_nn_distance(pts), sims, lower=True) <= 0.02  # nearer neighbours than the model
    assert out["cox"] > 2 and out["thomas"] > 2  # the same symptom from two different processes


def test_monte_carlo_p_counts_the_observation_among_the_simulations():
    assert monte_carlo_p(1.0, [2.0] * 99, lower=True) == pytest.approx(0.01)
    assert monte_carlo_p(3.0, [2.0] * 99, lower=True) == pytest.approx(1.0)


def test_the_same_checks_pass_a_correctly_specified_poisson_model():
    rng = np.random.default_rng(7)
    x = lambda xy: xy[:, 0]
    lam0 = lambda xy: np.exp(5.5 + x(xy))
    pts = simulate_poisson(lam0, UNIT, upper(lam0), rng)
    q, w = quadrature(UNIT, 100)
    b = fit_poisson_process(x(pts)[:, None], x(q)[:, None], w)["beta"]
    lam = lambda xy: np.exp(b[0] + b[1] * x(xy))
    g = grid_counts(pts, UNIT, cell=0.1)
    assert pearson_dispersion(g["counts"], g["area"] * lam(g["centres"]), 2) == pytest.approx(1, abs=0.35)
    sims = [mean_nn_distance(simulate_poisson(lam, UNIT, upper(lam), rng)) for _ in range(99)]
    assert monte_carlo_p(mean_nn_distance(pts), sims, lower=True) > 0.05


def test_the_window_area_enters_the_intensity():
    # 60 points in a 2 x 3 window: 10 per unit area, not 60
    rng = np.random.default_rng(8)
    pts = np.c_[rng.uniform(0, 2, 60), rng.uniform(0, 3, 60)]
    q, w = quadrature((0.0, 2.0, 0.0, 3.0), 30)
    r = fit_poisson_process(np.empty((60, 0)), np.empty((len(q), 0)), w)
    assert math.exp(r["beta"][0]) == pytest.approx(10)


def test_a_shifted_origin_cuts_the_window_into_partial_cells():
    # cell 0.5 with the origin at 0.25: edges at 0.25 and 0.75 in both directions, 3 x 3 cells
    g = grid_counts(np.array([[0.1, 0.1], [0.5, 0.5], [0.9, 0.5]]), UNIT, cell=0.5, origin=0.25)
    assert len(g["area"]) == 9 and g["area"].sum() == pytest.approx(1)
    assert sorted(set(np.round(g["area"], 4))) == [0.0625, 0.125, 0.25]
    centre = np.argmin(np.abs(g["centres"] - 0.5).sum(axis=1))
    assert g["area"][centre] == pytest.approx(0.25) and g["counts"][centre] == 1
