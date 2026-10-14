"""uvx --with numpy --with pytest pytest test_panel_fit.py

The small panels are worked out by hand; the random ones check a property over many draws.
"""

import numpy as np
import pytest

from panel_fit import decompose, fit, lag

UNIT = np.array(["A"] * 3 + ["B"] * 3)
TIME = np.array([0, 1, 2] * 2)


def test_a_unit_level_difference_makes_a_false_slope_that_unit_effects_remove():
    # y is constant within each unit; x rises within each unit and is higher in unit B
    x = np.array([0, 1, 2, 10, 11, 12.0])
    y = np.array([10, 10, 10, 20, 20, 20.0])
    assert fit(y, x[:, None], UNIT, TIME, "none")["coef"][0] == pytest.approx(150 / 154)
    assert fit(y, x[:, None], UNIT, TIME, "unit")["coef"][0] == pytest.approx(0, abs=1e-12)


def test_a_common_time_trend_makes_a_false_slope_that_time_effects_remove():
    # y is the year for every unit; x happens to rise over time too
    x = np.array([0, 1, 2, 1, 3, 3.0])
    y = TIME.astype(float)
    # unit-demeaned x: -1, 0, 1 and -4/3, 2/3, 2/3; y: -1, 0, 1 twice -> 4 / (14 / 3)
    assert fit(y, x[:, None], UNIT, TIME, "unit")["coef"][0] == pytest.approx(6 / 7)
    assert fit(y, x[:, None], UNIT, TIME, "twoway")["coef"][0] == pytest.approx(0, abs=1e-10)


def test_a_variable_that_never_changes_within_a_unit_cannot_be_estimated_with_unit_effects():
    x = np.array([0, 1, 2, 1, 3, 3.0])
    z = np.array([5, 5, 5, 7, 7, 7.0])  # an area, a region code
    y = x + z
    r = fit(y, np.c_[x, z], UNIT, TIME, "unit", names=["x", "z"])
    assert r["dropped"] == ["z"]
    assert r["coef"][0] == pytest.approx(1) and np.isnan(r["coef"][1])
    assert fit(y, np.c_[x, z], UNIT, TIME, "none", names=["x", "z"])["dropped"] == []


def test_two_way_effects_on_an_unbalanced_panel_match_dummy_regression():
    rng = np.random.default_rng(0)
    unit = np.repeat(np.arange(8), 5)
    time = np.tile(np.arange(5), 8)
    keep = rng.random(40) > 0.2
    unit, time = unit[keep], time[keep]
    x = rng.normal(size=len(unit))
    y = 2 * x + unit * 0.7 + time * 1.3 + rng.normal(size=len(unit))
    D = np.c_[x, np.eye(8)[unit], np.eye(5)[time][:, 1:]]
    expect = np.linalg.lstsq(D, y, rcond=None)[0][0]
    assert fit(y, x[:, None], unit, time, "twoway")["coef"][0] == pytest.approx(expect, abs=1e-8)


def test_cluster_robust_se_is_larger_when_errors_are_shared_within_a_unit():
    rng = np.random.default_rng(1)
    unit = np.repeat(np.arange(50), 10)
    time = np.tile(np.arange(10), 50)
    x = rng.normal(size=50)[unit] + 0.3 * rng.normal(size=500)  # x mostly varies between units
    y = x * 0 + rng.normal(size=50)[unit] + rng.normal(size=500) * 0.5
    r = fit(y, x[:, None], unit, time, "none", cluster=unit)
    assert r["se_cluster"][0] > 2 * r["se_naive"][0]


def test_cluster_robust_se_is_close_to_the_naive_one_when_errors_are_independent():
    rng = np.random.default_rng(2)
    unit = np.repeat(np.arange(100), 10)
    x = rng.normal(size=1000)
    y = 0.5 * x + rng.normal(size=1000)
    r = fit(y, x[:, None], unit, np.tile(np.arange(10), 100), "none", cluster=unit)
    assert 0.8 < r["se_cluster"][0] / r["se_naive"][0] < 1.25


def test_cluster_robust_se_by_hand_on_two_clusters():
    # one regressor, no intercept: se^2 = G/(G-1) (n-1)/(n-k) sum_g (sum x u)^2 / (sum x^2)^2
    x = np.array([1, 2, 1, 2.0])
    y = np.array([1, 3, 2, 3.0])
    g = np.array([0, 0, 1, 1])
    r = fit(y, x[:, None], g, np.array([0, 1, 0, 1]), "none", cluster=g, intercept=False)
    b = (x @ y) / (x @ x)  # 15 / 10
    u = y - b * x
    meat = (x[:2] @ u[:2]) ** 2 + (x[2:] @ u[2:]) ** 2
    assert r["coef"][0] == pytest.approx(1.5)
    assert r["se_cluster"][0] == pytest.approx(np.sqrt(2 / 1 * 3 / 3 * meat / 10**2))


def test_within_and_between_variation():
    # unit means 1 and 11 (between); deviations -1, 0, 1 in each unit (within)
    v = decompose(np.array([0, 1, 2, 10, 11, 12.0]), UNIT)
    assert v["between_var"] == pytest.approx(25)
    assert v["within_var"] == pytest.approx(2 / 3)
    assert v["within_share"] == pytest.approx((2 / 3) / (25 + 2 / 3))


def test_lag_takes_the_previous_time_of_the_same_unit_and_never_the_next():
    unit = np.array(["A", "B", "A", "A", "B"])
    time = np.array([2021, 2020, 2020, 2022, 2021])
    v = np.array([21.0, 200, 20, 22, 210])
    out = lag(v, unit, time, 1)
    assert np.isnan(out[2]) and np.isnan(out[1])  # first year of each unit
    assert out[0] == 20 and out[3] == 21 and out[4] == 200


def test_lag_does_not_jump_over_a_missing_year():
    out = lag(np.array([1.0, 3]), np.array(["A", "A"]), np.array([2020, 2022]), 1)
    assert np.isnan(out[1])  # 2021 is missing; 2020 is two years back
