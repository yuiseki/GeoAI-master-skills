"""uvx --with numpy --with duckdb --with pytest pytest test_shrink_rates.py"""

import numpy as np
import pytest

from shrink_rates import shrink


def test_small_denominators_move_towards_the_overall_rate_and_large_ones_stay():
    rng = np.random.default_rng(0)
    true = rng.beta(4, 16, size=500)  # rates around 0.2
    n = np.r_[np.full(250, 3), np.full(250, 3000)]
    x = rng.binomial(n, true)
    r = shrink(x, n)
    overall = x.sum() / n.sum()
    small, large = slice(0, 250), slice(250, 500)
    raw = x / n
    assert np.mean(np.abs(r["shrunk"][small] - overall)) < 0.5 * np.mean(np.abs(raw[small] - overall))
    assert np.allclose(r["shrunk"][large], raw[large], atol=0.01)


def test_shrunk_rates_are_closer_to_the_truth():
    rng = np.random.default_rng(1)
    true = rng.beta(2, 8, size=2000)
    n = rng.integers(1, 30, size=2000)
    x = rng.binomial(n, true)
    r = shrink(x, n)
    raw_err = np.mean((x / n - true) ** 2)
    shrunk_err = np.mean((r["shrunk"] - true) ** 2)
    assert shrunk_err < 0.6 * raw_err


def test_no_real_variation_shrinks_everything_to_the_overall_rate():
    rng = np.random.default_rng(2)
    n = rng.integers(1, 20, size=1000)
    x = rng.binomial(n, 0.3)  # every unit has the same true rate
    r = shrink(x, n)
    # Chance alone may leave a sliver of estimated variation, so the prior is very strong rather
    # than infinite; either way every unit lands next to the overall rate.
    assert r["prior_strength"] > 100
    assert np.max(np.abs(r["shrunk"] - x.sum() / n.sum())) < 0.03


def test_a_unit_with_no_denominator_gets_the_overall_rate_and_a_nan_raw_rate():
    r = shrink(np.array([0, 5, 1]), np.array([0, 10, 10]))
    assert np.isnan(r["raw"][0])
    assert r["shrunk"][0] == pytest.approx(6 / 20)


def test_exactly_no_variation_beyond_chance_gives_the_overall_rate():
    # Every unit has the overall rate exactly: the raw rates vary less than chance would make.
    r = shrink(np.array([3, 3, 3, 3]), np.array([10, 10, 10, 10]))
    assert r["prior_strength"] == np.inf
    assert np.allclose(r["shrunk"], 0.3)
