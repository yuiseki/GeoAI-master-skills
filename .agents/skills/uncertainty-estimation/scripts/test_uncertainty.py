"""uvx --with duckdb --with scikit-learn --with pytest pytest test_uncertainty.py"""

import numpy as np
import pytest
from sklearn.metrics import brier_score_loss

from uncertainty import calibration_table, conformal_intervals, coverage, ece


def test_ece_is_zero_when_each_bin_hits_its_mean_probability():
    p = np.array([0.1] * 10 + [0.7] * 10)
    y = np.array([1] + [0] * 9 + [1] * 7 + [0] * 3)
    assert ece(y, p, bins=10) == pytest.approx(0.0)


def test_ece_is_the_weighted_gap_between_probability_and_frequency():
    p = np.array([0.9] * 10 + [0.2] * 30)
    y = np.array([1] * 6 + [0] * 4 + [1] * 6 + [0] * 24)  # 0.6 observed vs 0.9; 0.2 vs 0.2
    assert ece(y, p, bins=10) == pytest.approx(10 / 40 * 0.3)


def test_overconfident_probabilities_have_a_larger_ece():
    rng = np.random.default_rng(0)
    p = rng.uniform(size=50_000)
    y = (rng.uniform(size=50_000) < p).astype(int)
    over = np.clip((p - 0.5) * 1.8 + 0.5, 0, 1)  # pushed towards 0 and 1
    assert ece(y, p) < 0.01
    assert ece(y, over) > 0.05


def test_calibration_table_reports_brier_like_sklearn():
    rng = np.random.default_rng(1)
    p = rng.uniform(size=1000)
    y = (rng.uniform(size=1000) < p).astype(int)
    t = calibration_table(y, p, bins=5)
    assert t["brier"] == pytest.approx(brier_score_loss(y, p))
    assert sum(b["n"] for b in t["bins"]) == 1000


def test_conformal_intervals_cover_about_the_promised_share():
    rng = np.random.default_rng(2)
    y = rng.normal(size=20_000)
    pred = np.zeros(20_000)
    lo, hi = conformal_intervals(y, pred, alpha=0.1)
    assert coverage(y, lo, hi) == pytest.approx(0.9, abs=0.01)


def test_each_interval_leaves_out_its_own_residual():
    # With 10 rows and alpha 0.1 the quantile is the largest of the other rows' residuals.
    y = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 100.0])
    pred = np.zeros(10)
    lo, hi = conformal_intervals(y, pred, alpha=0.1)
    assert hi[9] == pytest.approx(0.0)  # its own 100 does not widen its own interval
    assert coverage(y[9:], lo[9:], hi[9:]) == 0.0
    assert hi[0] == pytest.approx(100.0)


def test_coverage_by_group_shows_where_intervals_are_too_narrow():
    rng = np.random.default_rng(3)
    group = np.array(["calm"] * 9000 + ["noisy"] * 1000)
    y = np.r_[rng.normal(size=9000), rng.normal(scale=3, size=1000)]
    lo, hi = conformal_intervals(y, np.zeros(10_000), alpha=0.1)
    by = {g: coverage(y[group == g], lo[group == g], hi[group == g]) for g in ("calm", "noisy")}
    assert coverage(y, lo, hi) == pytest.approx(0.9, abs=0.015)
    assert by["calm"] > 0.9
    assert by["noisy"] < 0.7


@pytest.mark.parametrize("seed", range(5))
def test_leave_one_out_quantile_matches_brute_force_with_ties(seed):
    import math

    rng = np.random.default_rng(seed)
    y = rng.integers(0, 4, size=23).astype(float)  # many equal residuals
    pred = np.zeros(23)
    for alpha in (0.1, 0.2, 0.5):
        lo, hi = conformal_intervals(y, pred, alpha)
        r = np.abs(y)
        k = math.ceil((1 - alpha) * 23)  # m + 1 = 23
        for i in range(23):
            others = np.sort(np.delete(r, i))
            assert hi[i] == pytest.approx(others[k - 1])
