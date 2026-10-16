"""uvx --with duckdb --with scikit-learn --with pytest pytest test_uncertainty.py"""

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import brier_score_loss

from uncertainty import calibration_table, coverage, ece, held_out_group_intervals, split_intervals


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


def _leave_one_out_on_the_same_rows(y, pred, alpha):
    """The check this script no longer makes: each row's interval from the other rows' residuals,
    and coverage measured on those same rows."""
    r = np.abs(y - pred)
    k = math.ceil((1 - alpha) * len(r))
    q = np.array([np.sort(np.delete(r, i))[k - 1] for i in range(len(r))])
    return float(np.mean(r <= q))


def test_leave_one_out_on_the_same_rows_is_fixed_by_ranks_whatever_the_model():
    # Without ties a row is covered exactly when its residual is among the k smallest, so the
    # coverage is k / n however wrong the predictions are and however the noise varies.
    rng = np.random.default_rng(2)
    y = np.r_[rng.normal(size=107), rng.normal(10, 5, size=100)]
    for pred in (np.zeros(207), np.full(207, 50.0), rng.normal(size=207) * 30):
        assert _leave_one_out_on_the_same_rows(y, pred, 0.1) == pytest.approx(187 / 207)


def test_split_intervals_keep_the_promise_on_new_rows():
    # One fixed model, residuals of 99 calibration rows, coverage on separate test rows: on
    # average at least 1 - alpha and at most 1 - alpha + 1 / (m + 1).
    rng = np.random.default_rng(3)
    covered = []
    for _ in range(2000):
        x = rng.normal(size=199)
        y = x + rng.normal(size=199)
        cal = np.arange(199) < 99
        lo, hi = split_intervals(y, 0.8 * x, cal, alpha=0.1)
        assert np.isnan(lo[cal]).all()
        covered.append(coverage(y[~cal], lo[~cal], hi[~cal]))
    assert 0.9 - 0.003 < np.mean(covered) < 0.91 + 0.003


def test_split_intervals_use_only_the_calibration_rows():
    y = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1.0, 100, 100])
    cal = np.arange(12) < 10
    lo, hi = split_intervals(y, np.zeros(12), cal, alpha=0.1)  # k = ceil(0.9 * 11) = 10
    assert hi[10] == pytest.approx(1.0)
    assert coverage(y[~cal], lo[~cal], hi[~cal]) == 0.0


def test_too_few_calibration_rows_give_an_unbounded_interval():
    lo, hi = split_intervals(np.zeros(6), np.zeros(6), np.arange(6) < 5, alpha=0.1)
    assert hi[5] == np.inf


@pytest.mark.parametrize("seed", range(5))
def test_held_out_group_quantile_matches_brute_force_with_ties(seed):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 4, size=23).astype(float)  # many equal residuals
    groups = rng.integers(0, 4, size=23)
    for alpha in (0.1, 0.2, 0.5):
        lo, hi = held_out_group_intervals(y, np.zeros(23), groups, alpha)
        for i in range(23):
            others = np.sort(np.abs(y[groups != groups[i]]))
            k = math.ceil((1 - alpha) * (len(others) + 1))
            assert hi[i] == (others[k - 1] if k <= len(others) else np.inf)


def test_held_out_group_intervals_cover_about_the_promised_share_when_rows_are_alike():
    rng = np.random.default_rng(4)
    y = rng.normal(size=20_000)
    lo, hi = held_out_group_intervals(y, np.zeros(20_000), rng.integers(0, 5, size=20_000), 0.1)
    assert coverage(y, lo, hi) == pytest.approx(0.9, abs=0.01)


def test_held_out_group_coverage_falls_when_a_group_is_noisier():
    # Calibrated on the calm group, the noisy group's interval covers about 42%; the leave-one-out
    # check on the same rows would still report 90% overall.
    rng = np.random.default_rng(5)
    group = np.repeat(["calm", "noisy"], 5000)
    y = np.r_[rng.normal(size=5000), rng.normal(scale=3, size=5000)]
    lo, hi = held_out_group_intervals(y, np.zeros(10_000), group, alpha=0.1)
    noisy = group == "noisy"
    assert coverage(y[noisy], lo[noisy], hi[noisy]) == pytest.approx(0.42, abs=0.03)
    assert coverage(y, lo, hi) < 0.75
    assert _leave_one_out_on_the_same_rows(y[::10], np.zeros(1000), 0.1) == pytest.approx(0.9)


def test_coverage_by_group_shows_where_intervals_are_too_narrow():
    rng = np.random.default_rng(6)
    group = np.array(["calm"] * 9000 + ["noisy"] * 1000)
    y = np.r_[rng.normal(size=9000), rng.normal(scale=3, size=1000)]
    lo, hi = held_out_group_intervals(y, np.zeros(10_000), rng.integers(0, 5, size=10_000), 0.1)
    by = {g: coverage(y[group == g], lo[group == g], hi[group == g]) for g in ("calm", "noisy")}
    assert by["calm"] > 0.9
    assert by["noisy"] < 0.7


def test_isotonic_and_platt_recalibration_reduce_ece():
    from uncertainty import recalibrate

    rng = np.random.default_rng(10)
    true_p = rng.uniform(size=20_000)
    y = (rng.uniform(size=20_000) < true_p).astype(int)
    distorted = true_p ** 2.5  # too low everywhere but at the ends
    before = ece(y, distorted)
    iso = recalibrate(y, distorted, "isotonic", folds=5, seed=0)
    logit = np.log(true_p / (1 - true_p))
    underconfident = 1 / (1 + np.exp(-0.4 * logit))  # pulled towards 0.5
    platt = recalibrate(y, underconfident, "platt", folds=5, seed=0)
    assert before > 0.1
    assert ece(y, iso) < 0.02
    assert ece(y, platt) < 0.02


def test_recalibration_is_cross_fitted():
    from sklearn.isotonic import IsotonicRegression

    from uncertainty import recalibrate, recalibration_groups

    rng = np.random.default_rng(11)
    p = rng.uniform(size=300)
    y = (rng.uniform(size=300) < p).astype(int)
    out = recalibrate(y, p, "isotonic", folds=3, seed=4)
    groups = recalibration_groups(300, 3, 4)
    for g in range(3):
        held, rest = groups == g, groups != g
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(p[rest], y[rest])
        assert np.allclose(out[held], iso.predict(p[held]))


def test_calibrating_on_the_past_cannot_fix_a_rise_in_the_base_rate():
    from uncertainty import recalibrate

    rng = np.random.default_rng(12)
    time = np.repeat(np.arange(10), 2000)
    rate = np.where(time < 5, 0.2, 0.5)
    y = (rng.uniform(size=len(time)) < rate).astype(int)
    p = np.full(len(time), 0.2)  # a model that learned the old rate
    later = time >= 5
    past = recalibrate(y, p, "isotonic", time=time, calibrate_before=5)
    shuffled = recalibrate(y, p, "isotonic", folds=5, seed=0)
    assert ece(y[later], past[later]) > 0.25  # still 0.2 against 0.5
    assert ece(y[later], shuffled[later]) < ece(y[later], past[later])


def test_time_ordered_intervals_under_growing_noise():
    rng = np.random.default_rng(13)
    time = np.repeat(np.arange(10), 1000)
    y = rng.normal(scale=np.where(time < 5, 1.0, 2.0))
    later = time >= 5
    lo, hi = split_intervals(y, np.zeros(len(y)), ~later, alpha=0.1)
    assert np.isnan(lo[~later]).all()  # only rows after the calibration period get intervals
    assert coverage(y[later], lo[later], hi[later]) < 0.75


def test_ece_of_nothing_is_not_zero():
    assert np.isnan(ece(np.array([]), np.array([])))


def _intervals_cli(tmp_path, *args, role=False):
    import duckdb

    rng = np.random.default_rng(7)
    n = 400
    region = np.repeat(["a", "b"], n // 2)
    y = np.r_[rng.normal(size=n // 2), rng.normal(scale=3, size=n // 2)]
    roles = np.where(np.arange(n) % 2 == 0, "calibration", "test")
    con = duckdb.connect()
    con.execute("create table p (repeat int, model varchar, id varchar, target double, prediction double"
                + (", role varchar)" if role else ")"))
    con.executemany("insert into p values (?, ?, ?, ?, ?" + (", ?)" if role else ")"),
                    [(0, "m", str(i), float(y[i]), 0.0, *([roles[i]] if role else [])) for i in range(n)])
    con.execute("create table t as select * from (values " +
                ", ".join(f"('{i}', '{region[i]}')" for i in range(n)) + ") v(id, region)")
    con.execute(f"copy p to '{tmp_path}/p.parquet' (format parquet)")
    con.execute(f"copy t to '{tmp_path}/t.parquet' (format parquet)")
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("uncertainty.py")), "intervals",
                          f"{tmp_path}/p.parquet", "--table", f"{tmp_path}/t.parquet", "--id", "id", *args],
                         capture_output=True, text=True, check=True)
    return out.stdout


def test_cli_holds_out_the_groups_named_by_calibrate_by(tmp_path):
    out = _intervals_cli(tmp_path, "--calibrate-by", "region", "--by", "region")
    assert "held out by region" in out
    assert "region b: n 200, covered 0.4" in out


def test_cli_uses_the_role_column_for_a_split(tmp_path):
    out = _intervals_cli(tmp_path, role=True)
    assert "calibrated on the rows with role calibration" in out
    assert "n 200," in out
