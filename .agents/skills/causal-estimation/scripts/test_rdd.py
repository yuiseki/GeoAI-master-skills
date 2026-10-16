"""uvx --with numpy --with scipy --with pytest pytest test_rdd.py"""

import numpy as np
import pytest

from rdd import density_check, fuzzy, local_linear_jump, sharp


def test_noise_free_lines_give_the_exact_jump():
    x = np.linspace(-1, 1, 201)
    y = np.where(x >= 0, 3 + 2 * x, 1 + 0.5 * x)
    assert sharp(y, x, 0.0, 0.5)["tau"] == pytest.approx(2.0, abs=1e-10)


def test_triangular_weights_by_hand_on_one_side():
    # Points at 0.1, 0.2, 0.3 with h 0.4: weights 0.75, 0.5, 0.25. Weighted least squares in closed form.
    x = np.array([0.1, 0.2, 0.3])
    y = np.array([1.0, 3.0, 2.0])
    w = 1 - x / 0.4
    xb, yb = (w * x).sum() / w.sum(), (w * y).sum() / w.sum()
    slope = (w * (x - xb) * (y - yb)).sum() / (w * (x - xb) ** 2).sum()
    assert local_linear_jump(y, x, 0.0, 0.4, side=1)["intercept"] == pytest.approx(yb - slope * xb)
    # Equal weights would give another line: the weights matter here.
    assert local_linear_jump(y, x, 0.0, 0.4, side=1)["intercept"] != pytest.approx(np.polyfit(x, y, 1)[1])


def _world(seed, n=4000, tau=1.0, curve=0.0, noise=1.0):
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    y = tau * (x >= 0) + x + curve * x ** 2 * np.where(x >= 0, 3, -1) + rng.normal(scale=noise, size=n)
    return y, x


def test_a_wide_bandwidth_on_curved_sides_is_biased_and_a_narrow_one_less():
    wide, narrow = [], []
    for seed in range(30):
        y, x = _world(seed, curve=1.0)
        wide.append(sharp(y, x, 0.0, 1.0)["tau"])
        narrow.append(sharp(y, x, 0.0, 0.2)["tau"])
    assert abs(np.mean(wide) - 1) > 0.2
    assert abs(np.mean(narrow) - 1) < abs(np.mean(wide) - 1) / 3
    assert np.std(narrow) > np.std(wide)  # fewer rows: more variance


def test_robust_standard_errors_cover_when_the_sides_are_straight():
    covered = 0
    for seed in range(200):
        y, x = _world(100 + seed, n=2000)
        r = sharp(y, x, 0.0, 0.5)
        covered += abs(r["tau"] - 1) <= 1.96 * r["se"]
    assert 0.92 <= covered / 200 <= 0.98


def test_fuzzy_design_divides_the_outcome_jump_by_the_treatment_jump():
    rng = np.random.default_rng(3)
    n = 20000
    x = rng.uniform(-1, 1, n)
    d = (rng.random(n) < 0.2 + 0.5 * (x >= 0)).astype(float)  # the cutoff raises take-up by 0.5
    y = 2.0 * d + x + rng.normal(size=n)
    r = fuzzy(y, d, x, 0.0, 0.5)
    assert r["first_stage"] == pytest.approx(0.5, abs=0.03)
    assert r["tau"] == pytest.approx(2.0, abs=0.15)


def test_bunching_just_above_the_cutoff_shows_in_the_density_check():
    rng = np.random.default_rng(4)
    x = rng.uniform(-1, 1, 5000)
    moved = (x > -0.05) & (x < 0) & (rng.random(5000) < 0.7)  # people just below push themselves above
    x = np.where(moved, -x, x)
    assert density_check(x, 0.0, 0.05)["p"] < 0.001
    assert density_check(rng.uniform(-1, 1, 5000), 0.0, 0.05)["p"] > 0.01


def test_too_few_rows_on_a_side_stops():
    x = np.array([-0.5, -0.4, 0.1, 0.2, 0.3])
    with pytest.raises(SystemExit):
        sharp(np.ones(5), x, 0.0, 0.45)


def test_fuzzy_intervals_cover_with_the_first_stage_error_in_the_standard_error():
    # Most of the outcome's noise comes through the treatment; leaving the first stage's error out of the
    # delta method would inflate the standard error and over-cover.
    covered = 0
    for seed in range(200):
        rng = np.random.default_rng(500 + seed)
        n = 3000
        x = rng.uniform(-1, 1, n)
        d = (rng.random(n) < 0.2 + 0.5 * (x >= 0)).astype(float)
        y = 2.0 * d + x + 0.3 * rng.normal(size=n)
        r = fuzzy(y, d, x, 0.0, 0.5)
        covered += abs(r["tau"] - 2) <= 1.96 * r["se"]
    assert 0.92 <= covered / 200 <= 0.98
