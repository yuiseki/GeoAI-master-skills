"""uvx --with numpy --with duckdb --with pytest pytest test_error_breakdown.py"""

import numpy as np
import pytest

from error_breakdown import breakdown


def test_bias_and_mae_per_group():
    target = np.array([1.0, 2.0, 3.0, 10.0, 10.0])
    pred = np.array([2.0, 3.0, 4.0, 7.0, 9.0])
    group = np.array(["a", "a", "a", "b", "b"])
    rows = {r["group"]: r for r in breakdown(target, pred, group)}
    assert rows["a"]["n"] == 3 and rows["a"]["bias"] == pytest.approx(1.0)
    assert rows["b"]["bias"] == pytest.approx(-2.0) and rows["b"]["mae"] == pytest.approx(2.0)
    assert rows["b"]["rmse"] == pytest.approx(np.sqrt((9 + 1) / 2))


def test_numeric_columns_are_cut_into_quantile_bins():
    x = np.arange(100, dtype=float)
    target = np.zeros(100)
    pred = x / 100  # error grows with x
    rows = breakdown(target, pred, x, bins=4)
    assert len(rows) == 4
    assert all(r["n"] == 25 for r in rows)
    assert rows[0]["mae"] < rows[-1]["mae"]


def test_weights_enter_the_group_scores():
    target = np.zeros(3)
    pred = np.array([1.0, 1.0, 4.0])
    w = np.array([1.0, 1.0, 2.0])
    (row,) = breakdown(target, pred, np.array(["a", "a", "a"]), weights=w)
    assert row["mae"] == pytest.approx((1 + 1 + 8) / 4)
    assert row["weight"] == pytest.approx(4.0)
