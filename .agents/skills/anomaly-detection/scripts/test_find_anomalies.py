"""uvx --with duckdb --with scikit-learn --with pytest pytest test_find_anomalies.py"""

import numpy as np
import pytest

from find_anomalies import (
    expected_from_neighbors,
    expected_from_time,
    global_scores,
    robust_scores,
)


def test_time_expectation_stays_within_each_unit():
    # Two units at very different levels; each is flat except one spike in unit a.
    unit = np.array(["a"] * 10 + ["b"] * 10)
    time = np.r_[np.arange(10), np.arange(10)]
    x = np.r_[np.full(10, 50.0), np.full(10, 80.0)]
    x[4] = 20.0
    exp = expected_from_time(x, unit, time, window=2, past_only=False)
    assert exp[4] == pytest.approx(50.0)
    assert np.allclose(exp[10:], 80.0)  # unit b is not pulled towards unit a
    s = robust_scores(x, exp)
    assert int(np.argmax(s)) == 4


def test_time_expectation_excludes_the_row_itself():
    unit = np.array(["a"] * 3)
    time = np.arange(3)
    x = np.array([100.0, 10.0, 10.0])
    exp = expected_from_time(x, unit, time, window=1, past_only=False)
    # At the edge the only other period is row 1; with itself included the median would be 55.
    assert exp[0] == pytest.approx(10.0)


def test_past_only_uses_no_later_period():
    unit = np.array(["a"] * 6)
    time = np.arange(6)
    x = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 99.0])
    exp = expected_from_time(x, unit, time, window=2, past_only=True)
    assert exp[4] == pytest.approx(10.0)  # the later 99 does not reach row 4
    assert np.isnan(exp[0])  # nothing before the first period


def test_time_follows_the_time_column_not_the_row_order():
    unit = np.array(["a"] * 5)
    time = np.array([4, 0, 3, 1, 2])
    x = np.array([14.0, 10.0, 13.0, 11.0, 12.0])  # a straight line over time
    exp = expected_from_time(x, unit, time, window=1, past_only=False)
    # Row with time 2 (x=12) sits between times 1 and 3 (11 and 13).
    assert exp[4] == pytest.approx(12.0)


def test_spatial_expectation_uses_the_nearest_other_units():
    lon = np.array([0.0, 0.5, 1.0, 0.0, 0.5, 30.0])
    lat = np.array([60.0, 60.0, 60.0, 60.5, 60.5, 0.0])
    x = np.array([10.0, 10.0, 10.0, 10.0, 40.0, 10.0])
    exp = expected_from_neighbors(x, lon, lat, k=3)
    assert exp[4] == pytest.approx(10.0)
    assert int(np.argmax(robust_scores(x, exp))) == 4


def test_robust_scale_is_not_swamped_by_one_huge_outlier():
    rng = np.random.default_rng(0)
    exp = np.zeros(200)
    x = rng.normal(size=200)
    x[0] = 1000.0
    x[1] = 6.0  # moderate, but clearly out
    s = robust_scores(x, exp)
    assert s[1] > 4  # a standard deviation would be inflated by row 0 and hide row 1


def test_global_scores_rank_a_multivariate_outlier_first():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(200, 3))
    X[7] = [4.0, -4.0, 4.0]
    s = global_scores(X, seed=0)
    assert int(np.argmax(s["isolation_forest"])) == 7
    assert int(np.argmax(s["lof"])) == 7


def test_a_zero_mad_falls_back_and_says_so():
    from find_anomalies import robust_scale

    r = np.r_[np.zeros(80), np.ones(20)]  # mostly zero, like sparse counts
    scale, which = robust_scale(r)
    assert scale > 0 and "MAD is 0" in which
    with pytest.raises(SystemExit):
        robust_scale(np.zeros(10))
