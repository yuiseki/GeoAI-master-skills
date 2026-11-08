"""uvx --python 3.12 --with numpy --with 'duckdb>=1.5.5' --with scipy --with pyproj --with pytest pytest -q -p no:cacheprovider test_verify_drawdown.py"""

# moran (k nearest neighbours, row-standardised) of verify_drawdown.py.
import numpy as np
import pytest

from verify_drawdown import moran


def line(n):
    return np.column_stack([np.arange(n, dtype=float), np.zeros(n)])


def test_moran_alternating_values_on_a_line():
    # k = 2: an inner point's neighbours are both of the other value (-0.25 each); an end point has one of each (0).
    # sum z W z = 8 * -0.25 = -2, sum z^2 = 10 * 0.25 = 2.5, n / W.sum() = 1 -> I = -0.8
    i, p = moran(np.array([0.0, 1.0] * 5), line(10), k=2, n_perm=99)
    assert i == pytest.approx(-0.8) and p == 1.0


def test_moran_two_halves_on_a_line():
    # 0 x 5 then 1 x 5, k = 1, on points whose gaps grow (0, 1, 3, 6, ...: no ties): each point's nearest is the one
    # before it (point 0: point 1), so only point 5 pairs across the step: sum z W z = 9 * 0.25 - 0.25 = 2, I = 0.8
    x = np.cumsum(np.arange(10, dtype=float))
    i, p = moran(np.array([0.0] * 5 + [1.0] * 5), np.column_stack([x, np.zeros(10)]), k=1, n_perm=199)
    assert i == pytest.approx(0.8) and p < 0.05
