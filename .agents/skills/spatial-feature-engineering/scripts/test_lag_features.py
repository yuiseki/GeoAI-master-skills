"""uvx --with numpy --with duckdb --with pytest pytest test_lag_features.py"""

import numpy as np
import pytest

from lag_features import lag_features


def test_lags_rolling_means_and_totals_use_only_earlier_periods():
    unit = np.array(["a"] * 5 + ["b"] * 5)
    time = np.r_[np.arange(5), np.arange(5)]
    value = np.r_[np.array([1, 2, 3, 4, 5.0]), np.array([10, 20, 30, 40, 50.0])]
    f = lag_features(unit, time, value, lags=[1, 2], windows=[2], cumulative=True)
    a = slice(0, 5)
    assert np.isnan(f["lag1"][0]) and f["lag1"][a][1:].tolist() == [1, 2, 3, 4]
    assert f["lag2"][a][2:].tolist() == [1, 2, 3]
    # Mean of the 2 periods before t (not including t).
    assert np.isnan(f["mean2"][0]) and np.isnan(f["mean2"][1])
    assert f["mean2"][a][2:].tolist() == [1.5, 2.5, 3.5]
    # Total of everything before t.
    assert f["total_before"][a].tolist() == [0, 1, 3, 6, 10]
    # Unit b does not borrow from unit a.
    assert np.isnan(f["lag1"][5]) and f["lag1"][6] == 10


def test_rows_out_of_order_and_gaps_in_time():
    unit = np.array(["a", "a", "a", "a"])
    time = np.array([3, 0, 1, 4])  # period 2 is missing
    value = np.array([30.0, 0.0, 10.0, 40.0])
    f = lag_features(unit, time, value, lags=[1], windows=[], cumulative=False)
    # A lag is the value one period earlier in time, not one row earlier: t=3 has no t=2.
    assert np.isnan(f["lag1"][1])  # t=0 has no earlier period
    assert f["lag1"][2] == 0.0  # t=1 <- t=0
    assert np.isnan(f["lag1"][0])  # t=3 <- t=2 is missing
    assert f["lag1"][3] == 30.0  # t=4 <- t=3


def test_the_current_value_never_enters():
    rng = np.random.default_rng(0)
    unit = np.repeat(["a", "b", "c"], 50)
    time = np.tile(np.arange(50), 3)
    value = rng.normal(size=150)
    f = lag_features(unit, time, value, lags=[1, 3], windows=[3, 6], cumulative=True)
    for k, v in f.items():
        ok = ~np.isnan(v)
        # Features built from the past cannot track the current value of white noise.
        assert abs(np.corrcoef(v[ok], value[ok])[0, 1]) < 0.3, k


def test_a_gap_inside_the_window_makes_the_mean_nan_but_the_total_counts_what_exists():
    unit = np.array(["a"] * 4)
    time = np.array([0, 1, 3, 4])  # period 2 missing
    value = np.array([1.0, 2.0, 4.0, 8.0])
    f = lag_features(unit, time, value, lags=[], windows=[2], cumulative=True)
    assert np.isnan(f["mean2"][2])  # t=3 needs t=1 and t=2
    assert np.isnan(f["mean2"][3])  # t=4 needs t=3 and t=2
    assert f["total_before"].tolist() == [0, 1, 3, 7]


def test_two_rows_for_one_period_are_refused():
    with pytest.raises(SystemExit):
        lag_features(np.array(["a", "a"]), np.array([1, 1]), np.array([1.0, 2.0]))
