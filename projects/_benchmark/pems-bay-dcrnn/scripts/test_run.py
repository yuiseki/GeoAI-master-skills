"""uvx --python 3.12 --with numpy --with pytest pytest -q -p no:cacheprovider test_run.py"""

# day_of, per_day, boot_days and batches of run.py (no torch: run.py imports it only inside the model functions).
import numpy as np
import pytest

import run

DAY = 86400 * 10**9


def test_day_of_counts_utc_days_of_the_target_time():
    p = {"t": np.array([0, DAY - 1, DAY, 3 * DAY + 5], dtype="int64")}
    assert run.day_of(p, np.array([0, 1]), 1).tolist() == [0, 1]
    assert run.day_of(p, np.array([0]), 3).tolist() == [3]


def test_per_day_leaves_out_missing_truth():
    err = np.array([[1.0, -2.0], [3.0, 4.0], [5.0, 6.0]])
    truth = np.array([[60.0, 0.0], [55.0, 50.0], [0.0, 0.0]])   # 0 = missing reading
    u, s, c = run.per_day(err, truth, np.array([10, 10, 11]))
    assert u.tolist() == [10, 11] and s.tolist() == [1 + 3 + 4, 0] and c.tolist() == [3, 0]


def test_boot_days_is_a_ratio_of_resampled_sums():
    lo, hi = run.boot_days(np.array([6.0, 6.0]), np.array([3, 3]))
    assert (lo, hi) == (2.0, 2.0)
    lo, hi = run.boot_days(np.array([3.0, 9.0]), np.array([3, 3]), reps=4000)
    assert (lo, hi) == (1.0, 3.0)                       # a quarter of the draws take one day twice


def test_batches_scale_the_speed_and_keep_the_time_of_day():
    values = np.arange(60, dtype=float).reshape(30, 2)
    tod = np.linspace(0, 1, 30, endpoint=False)
    p = {"values": values, "tod": tod, "mean": 10.0, "sd": 2.0}
    out = list(run.batches(p, np.array([11, 12, 13]), bs=2))
    assert [len(s) for s, _, _ in out] == [2, 1]
    s, x, y = out[0]
    assert x.dtype == np.float32 and x.shape == (2, 12, 2, 2) and y.shape == (2, 12, 2)
    assert x[0, -1, 0, 0] == pytest.approx((values[11, 0] - 10.0) / 2.0) and x[0, -1, 0, 1] == pytest.approx(tod[11])
    assert y[0, 0, 1] == values[12, 1]                  # targets stay in km/h
    rng_order = [s.tolist() for s, _, _ in run.batches(p, np.array([11, 12, 13]), bs=3, rng=np.random.default_rng(0))]
    assert sorted(rng_order[0]) == [11, 12, 13]
