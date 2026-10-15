"""uvx --with numpy --with pytest pytest test_st_model.py

The small grids are worked out by hand; the simulated worlds check a property of one seeded draw.
"""

import numpy as np
import pytest

from st_model import (ar1_forecast, evaluate, fit, fit_phi, idw, lag1_autocorrelation, moran, predict,
                      residual_diagnostics, separability_ratio, simulate)

# 2 locations x 3 times: mu 10, a = (-1, 1), b = (-2, 0, 2)
LOC = np.array([0, 0, 0, 1, 1, 1])
T = np.array([0, 1, 2, 0, 1, 2.0])
Y = 10 + np.array([-1, -1, -1, 1, 1, 1]) + np.array([-2, 0, 2, -2, 0, 2.0])
XY = {0: (0.0, 0.0), 1: (1.0, 0.0)}


def test_the_additive_decomposition_is_exact_on_a_small_grid_even_with_a_missing_cell():
    keep = np.arange(6) != 4  # location 1 at time 1 missing
    p = fit("additive", LOC[keep], T[keep], Y[keep], XY)
    assert predict(p, LOC, T, XY) == pytest.approx(Y)  # the missing cell is filled as 10 + 1 + 0


def test_space_only_and_time_only_leave_the_other_part_in_the_residual():
    ps = fit("space", LOC, T, Y, XY)
    pt = fit("time", LOC, T, Y, XY)
    assert Y - predict(ps, LOC, T, XY) == pytest.approx([-2, 0, 2, -2, 0, 2])
    assert Y - predict(pt, LOC, T, XY) == pytest.approx([-1, -1, -1, 1, 1, 1])


def test_location_specific_trends_need_the_interaction():
    # location 0 rises by 1 a step, location 1 falls by 1 a step
    y = np.array([0, 1, 2, 2, 1, 0.0])
    add = fit("additive", LOC, T, y, XY)
    inter = fit("interaction", LOC, T, y, XY)
    assert np.abs(y - predict(add, LOC, T, XY)).max() == pytest.approx(1)
    assert predict(inter, LOC, T, XY) == pytest.approx(y)


def test_a_new_location_takes_the_inverse_distance_mean_of_its_neighbours():
    # neighbours at distances 1 and 3 with effects 4 and 8: (4 + 8/3) / (1 + 1/3) = 5
    assert idw((0, 0), [(1, 0), (3, 0)], [4, 8], k=2) == pytest.approx(5)


def test_an_ar1_effect_decays_by_phi_to_the_gap_even_when_times_are_irregular():
    assert ar1_forecast(1.0, 0.5, 2) == pytest.approx(0.25)
    times = np.array([0, 1, 3, 4, 7.0])
    assert fit_phi(times, 0.6 ** times) == pytest.approx(0.6, abs=1e-3)


def test_moran_and_lag1_autocorrelation_by_hand():
    # a line of 4 with neighbours 1-2, 2-3, 3-4: z = 1, 1, -1, -1; sum w z z = 2; I = 4/6 x 2/4
    W = np.array([[0, 1, 0, 0], [1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0.0]])
    assert moran(np.array([1, 1, -1, -1.0]), W) == pytest.approx(1 / 3)
    # one location alternating 1, -1, 1, -1: sum of z_t z_t+1 = -3 over sum z^2 = 4
    assert lag1_autocorrelation(np.zeros(4), np.arange(4.0), np.array([1, -1, 1, -1.0])) == pytest.approx(-0.75)


def _diag(world, model, seed=0):
    d = simulate(world, seed=seed)
    p = fit(model, d["loc"], d["t"], d["y"], d["coords"])
    return residual_diagnostics(d["loc"], d["t"], d["y"] - predict(p, d["loc"], d["t"], d["coords"]), d["coords"])


def test_in_an_additive_world_each_one_sided_model_leaves_the_other_dependence():
    space, time, add = (_diag("additive", m) for m in ("space", "time", "additive"))
    assert space["temporal"] > 0.5 and abs(space["spatial"]) < 0.1
    assert time["spatial"] > 0.3 and abs(time["temporal"]) < 0.1
    assert abs(add["spatial"]) < 0.1 and abs(add["temporal"]) < 0.1


def test_in_an_interaction_world_the_additive_model_leaves_both():
    add, inter = _diag("interaction", "additive"), _diag("interaction", "interaction")
    assert add["temporal"] > 0.5 and add["spatial"] > inter["spatial"] + 0.1  # weak near the middle time
    assert abs(inter["temporal"]) < 0.1 and abs(inter["spatial"]) < 0.1


def test_random_rows_flatter_and_each_one_sided_split_misses_one_kind_of_error():
    # additive world: a random test cell has its location and its time in training; the others do not
    d = simulate("additive", seed=1)
    r = evaluate(["additive"], d["loc"], d["t"], d["y"], d["coords"], cutoff=np.quantile(d["t"], 0.7), seed=1)
    rmse = {k: v["additive"] for k, v in r.items()}
    assert rmse["random"] < 0.9 * min(rmse["future_known"], rmse["new_location"])
    assert rmse["future_new"] > max(rmse["future_known"], rmse["new_location"])


def test_the_splits_keep_what_they_promise():
    d = simulate("additive", seed=2, n_loc=20, n_t=10)
    r = evaluate(["mean"], d["loc"], d["t"], d["y"], d["coords"], cutoff=5, seed=2, return_masks=True)
    for train, test in r["masks"]["future_new"]:
        assert not set(d["loc"][train]) & set(d["loc"][test])
        assert d["t"][train].max() <= 5 < d["t"][test].min()
    for train, test in r["masks"]["future_known"]:
        assert set(d["loc"][test]) <= set(d["loc"][train])
    for train, test in r["masks"]["new_location"]:
        assert not set(d["loc"][train]) & set(d["loc"][test])
        assert set(d["t"][test]) <= set(d["t"][train])


def test_separable_covariance_has_a_ratio_near_one_and_a_moving_field_does_not():
    sep = simulate("separable", seed=3, n_loc=60, n_t=60, noise=0)
    adv = simulate("advection", seed=3, n_loc=60, n_t=60, noise=0)
    east = (1, 0)
    rs = separability_ratio(sep["loc"], sep["t"], sep["y"], sep["coords"], dist=(0.05, 0.15), lag=3, direction=east)
    ra = separability_ratio(adv["loc"], adv["t"], adv["y"], adv["coords"], dist=(0.05, 0.15), lag=3, direction=east)
    every = separability_ratio(adv["loc"], adv["t"], adv["y"], adv["coords"], dist=(0.05, 0.15), lag=3)
    assert rs == pytest.approx(1, abs=0.2)
    assert ra > 1.5 and ra > every  # the field drifts east by 0.09 in 3 steps


def test_missing_cells_and_irregular_times_are_handled():
    d = simulate("additive", seed=4, missing=0.2, irregular_time=True)
    assert len(d["y"]) < d["n_loc"] * d["n_t"]
    assert len(set(np.diff(np.unique(d["t"])))) > 1
    p = fit("additive", d["loc"], d["t"], d["y"], d["coords"])
    res = d["y"] - predict(p, d["loc"], d["t"], d["coords"])
    assert np.std(res) < 0.7  # the noise sd is 0.5


def test_a_model_that_wins_on_random_rows_can_lose_on_the_future():
    # persistent space-time residuals look like per-location trends inside the training period
    d = simulate("separable", seed=1)
    r = evaluate(["mean", "interaction"], d["loc"], d["t"], d["y"], d["coords"], cutoff=np.quantile(d["t"], 0.7),
                 seed=1)
    assert r["random"]["interaction"] < r["random"]["mean"]
    assert r["future_known"]["interaction"] > r["future_known"]["mean"]


def test_a_future_time_decays_the_last_effect_and_a_time_between_is_interpolated():
    p = {"model": "time", "mu": 10.0, "a": {}, "b": {0.0: 0.5, 1.0: 1.0, 3.0: -1.0}, "c": {}, "tbar": 0.0,
         "phi": 0.5, "coords": {}}
    # 2 steps after the last time: -1 x 0.5^2; at 1.5, a quarter of the way from 1.0 to -1.0
    assert predict(p, np.array([0, 0]), np.array([5.0, 1.5]), {0: (0, 0)}) == pytest.approx([9.75, 10.5])


def test_a_new_location_gets_its_effect_from_the_neighbours_not_zero():
    p = fit("space", LOC, T, Y, XY)  # a = -1 at x = 0, +1 at x = 1; mu = 10
    # at x = 0.25: weights 4 and 4/3 -> (-4 + 4/3) / (16/3) = -0.5
    assert predict(p, np.array([9]), np.array([0.0]), {**XY, 9: (0.25, 0.0)}) == pytest.approx([9.5])


def test_lag1_autocorrelation_follows_time_not_row_order():
    t = np.array([2, 0, 3, 1.0])
    r = np.array([1, 1, -1, -1.0])  # in time order: 1, -1, 1, -1
    assert lag1_autocorrelation(np.zeros(4), t, r) == pytest.approx(-0.75)
