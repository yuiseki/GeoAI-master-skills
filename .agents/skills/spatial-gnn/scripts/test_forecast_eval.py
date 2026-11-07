"""uvx --python 3.12 --with numpy --with pytest pytest -q test_forecast_eval.py"""

import numpy as np
import pytest

from forecast_eval import (boot_ratio, day_sums, historical_average, last_value, make_xy, masked_metrics,
                           paired_day_sums, share_of_gain, split_counts, time_in_day, window_starts)


def test_windows_and_split_follow_the_author_script():
    starts = window_starts(100, 12, 12)
    assert starts[0] == 11 and starts[-1] == 100 - 12 - 1 and len(starts) == 100 - 23
    tr, va, te = split_counts(len(starts))
    assert tr == round(0.7 * len(starts)) and te == round(0.2 * len(starts)) and tr + va + te == len(starts)


def test_make_xy_and_last_value_line_up():
    v = np.arange(40, dtype=float).reshape(20, 2)
    tod = np.linspace(0, 1, 20, endpoint=False)
    x, y = make_xy(v, tod, np.array([11]), 12, 3)
    assert x.shape == (1, 12, 2, 2) and y.shape == (1, 3, 2)
    assert x[0, -1, 0, 0] == v[11, 0] and x[0, 0, 0, 0] == v[0, 0] and y[0, 0, 1] == v[12, 1]
    assert x[0, -1, 1, 1] == tod[11]
    assert np.array_equal(last_value(v, np.array([11]))[0], x[0, -1, :, 0])


def test_time_in_day():
    t = np.array([0, 6 * 3600, 23 * 3600 + 55 * 60], dtype="int64") * 10**9
    assert np.allclose(time_in_day(t), [0, 0.25, (23 * 60 + 55) / 1440])


def test_masked_metrics_leave_out_zeros():
    m = masked_metrics(np.array([10.0, 55.0, 57.0]), np.array([0.0, 50.0, 60.0]))
    assert m["mae"] == pytest.approx(4.0) and m["rmse"] == pytest.approx(np.sqrt(17))
    assert m["mape"] == pytest.approx((5 / 50 + 3 / 60) / 2)


def test_historical_average_recovers_a_weekly_pattern_and_skips_zeros():
    week = 7 * 288
    v = np.tile(np.sin(np.arange(week) / 50.0) * 10 + 60, 6)[:, None].repeat(3, 1)
    target = np.array([5 * week + 100, 5 * week + 2000])
    assert np.allclose(historical_average(v, target), v[target])
    v2 = v.copy()
    v2[4 * week + 100, 0] = 0.0
    assert historical_average(v2, target[:1])[0, 0] == pytest.approx(v[target[0], 0])


def test_paired_day_sums_equal_the_difference_of_masked_mae():
    truth = np.array([[10.0, 0.0], [10.0, 10.0], [20.0, 20.0]])
    a = np.array([[12.0, 5.0], [10.0, 10.0], [20.0, 20.0]])
    b = np.array([[11.0, 9.0], [11.0, 13.0], [20.0, 21.0]])
    days = np.array([0, 0, 1])
    u, s, c = paired_day_sums(a, b, truth, days)
    assert list(u) == [0, 1] and np.allclose(s, [2 - 1 - 1 - 3, -1]) and list(c) == [3, 2]
    assert s.sum() / c.sum() == pytest.approx(masked_metrics(a, truth)["mae"] - masked_metrics(b, truth)["mae"])
    _, sa, ca = day_sums(a, truth, days)
    assert sa.sum() / ca.sum() == pytest.approx(masked_metrics(a, truth)["mae"])


def test_boot_ratio_resamples_whole_groups():
    lo, hi = boot_ratio(np.array([1.0, 1.0, 1.0]), np.array([1, 2, 3]), reps=500)
    assert 1 / 3 - 1e-9 <= lo <= hi <= 1 + 1e-9
    lo, hi = boot_ratio(np.array([2.0, 4.0]), np.array([1, 2]), reps=200)
    assert lo == pytest.approx(2.0) and hi == pytest.approx(2.0)


def test_share_of_gain_splits_the_total():
    truth = np.array([[10.0, 20.0]])
    a, b = np.array([[13.0, 21.0]]), np.array([[10.0, 20.0]])
    m = np.array([[True, False]])
    assert share_of_gain(a, b, truth, m) == pytest.approx(0.75)
    assert share_of_gain(a, b, truth, m) + share_of_gain(a, b, truth, ~m) == pytest.approx(1.0)
