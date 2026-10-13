"""uvx --with duckdb --with numpy --with pytest pytest test_noise_ceiling.py"""

import numpy as np
import pytest

from noise_ceiling import counts_ceiling, repeat_ceiling, rounding_ceiling


def r2(y, pred):
    return 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def test_repeat_ceiling_is_the_correlation_not_its_square():
    # Two independent measurements of the same signal with equal noise: reliability 0.6.
    rng = np.random.default_rng(0)
    n = 200_000
    s = rng.normal(scale=np.sqrt(0.6), size=n)
    y1 = s + rng.normal(scale=np.sqrt(0.4), size=n)
    y2 = s + rng.normal(scale=np.sqrt(0.4), size=n)
    c = repeat_ceiling(y1, y2)
    # A model that knew the signal exactly would score R2 = 0.6 on y1.
    assert r2(y1, s) == pytest.approx(0.6, abs=0.01)
    assert c["ceiling_r2"] == pytest.approx(0.6, abs=0.01)
    # Predicting y1 by the other noisy measurement gives only r squared.
    assert c["other_measurement_r2"] == pytest.approx(0.36, abs=0.01)


def test_repeat_ceiling_ignores_a_shift_between_measurements():
    rng = np.random.default_rng(1)
    s = rng.normal(size=50_000)
    y1 = s + rng.normal(scale=0.5, size=50_000)
    y2 = 10 + 2 * s + rng.normal(scale=1.0, size=50_000)  # another period, faster overall
    c = repeat_ceiling(y1, y2)
    assert c["ceiling_r2"] == pytest.approx(0.8, abs=0.01)


def test_counts_ceiling_matches_the_share_of_variance_in_the_rate():
    rng = np.random.default_rng(2)
    lam = rng.gamma(shape=0.5, scale=4.0, size=200_000)  # rates vary a lot between units
    y = rng.poisson(lam)
    c = counts_ceiling(y)
    truth = lam.var() / (lam.var() + lam.mean())
    assert c["ceiling_r2"] == pytest.approx(truth, abs=0.01)
    assert r2(y.astype(float), lam) == pytest.approx(truth, abs=0.01)


def test_counts_with_no_extra_variation_have_no_ceiling():
    rng = np.random.default_rng(3)
    y = rng.poisson(3.0, size=100_000)
    c = counts_ceiling(y)
    assert abs(c["ceiling_r2"]) < 0.02


def test_counts_with_exposure():
    # Units observed for different lengths (cell areas, years); the rate per exposure varies.
    rng = np.random.default_rng(4)
    exposure = rng.uniform(0.5, 2.0, size=200_000)
    rate = rng.gamma(shape=1.0, scale=2.0, size=200_000)
    y = rng.poisson(rate * exposure)
    c = counts_ceiling(y, exposure)
    mu = rate * exposure
    assert c["ceiling_r2"] == pytest.approx(r2(y.astype(float), mu), abs=0.01)


def test_rounding_ceiling():
    rng = np.random.default_rng(5)
    x = rng.uniform(0, 40, size=200_000)
    y = np.round(x / 5) * 5  # rounded to the nearest 5
    c = rounding_ceiling(y, step=5)
    assert c["noise_variance"] == pytest.approx(25 / 12)
    assert c["ceiling_r2"] == pytest.approx(r2(y, x), abs=0.01)


def test_split_half_ceiling_for_the_total_uses_spearman_brown():
    # Each half of a period measures the same signal with independent noise; the target is the
    # total of the two halves, which is less noisy than either half.
    rng = np.random.default_rng(6)
    n = 200_000
    s = rng.normal(size=n)
    h1 = s + rng.normal(scale=1.0, size=n)
    h2 = s + rng.normal(scale=1.0, size=n)
    total = h1 + h2
    c = repeat_ceiling(h1, h2, halves_of_target=True)
    assert c["r"] == pytest.approx(0.5, abs=0.01)
    assert r2(total, 2 * s) == pytest.approx(2 / 3, abs=0.01)
    assert c["ceiling_r2"] == pytest.approx(2 / 3, abs=0.01)
