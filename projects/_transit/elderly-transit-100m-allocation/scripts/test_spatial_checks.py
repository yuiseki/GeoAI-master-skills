"""uvx --python 3.12 --with numpy --with pandas --with scipy --with pytest pytest -q -p no:cacheprovider test_spatial_checks.py"""

import numpy as np
import pytest

from spatial_checks import indices, moran, queen_weights


def test_indices_count_rows_and_columns_across_mesh_borders():
    # 53394509 and 53394600 are east-west neighbours across a second-level mesh border.
    i1, j1 = indices("53394509")
    i2, j2 = indices("53394600")
    assert i1 == i2 and j2 == j1 + 1
    # 1 km rows: 80 per first-level mesh (8 x 10); 53 -> row 53 * 80.
    assert indices("53390000") == (53 * 80, 39 * 80)


def test_queen_weights_are_row_standardised_with_8_neighbours_in_the_middle():
    codes = [f"533945{i}{j}" for i in (1, 2, 3) for j in (1, 2, 3)]          # 3 x 3 block of 1 km cells
    w = queen_weights(codes).toarray()
    assert np.allclose(w.sum(axis=1), 1.0)
    nonzero = (w > 0).sum(axis=1)
    assert nonzero[codes.index("53394522")] == 8
    assert nonzero[codes.index("53394511")] == 3 and nonzero[codes.index("53394512")] == 5
    assert w[codes.index("53394522"), codes.index("53394511")] == pytest.approx(1 / 8)


def test_queen_weights_isolated_cell_has_no_neighbours():
    w = queen_weights(["53394511", "53394599"]).toarray()
    assert (w == 0).all()


def line(n):
    return [f"5339450{j}" for j in range(n)]          # one row of 1 km cells, west to east


def test_moran_alternating_values_is_minus_one():
    # Every neighbour has the opposite deviation, so W z = -z exactly and I = -1.
    r = moran([0, 1] * 5, line(10), permutations=99)
    assert r["n"] == 10 and r["I"] == pytest.approx(-1.0)
    assert r["p_positive"] == 1.0


def test_moran_two_blocks_by_hand():
    # z = -0.5 x 5, +0.5 x 5. Every cell but the two at the step has all neighbours on its own side:
    # sum z W z = 8 * 0.25 = 2, sum z^2 = 2.5 -> I = 0.8.
    r = moran([0] * 5 + [1] * 5, line(10), permutations=199)
    assert r["I"] == pytest.approx(0.8)
    assert r["mean"] == 0.5 and r["neighbors_mean"] == pytest.approx(1.0)
    assert r["p_positive"] < 0.05


def test_moran_drops_missing_and_refuses_small_or_constant_input():
    r = moran([0, 1] * 5 + [np.nan], line(10) + ["53394599"], permutations=9)
    assert r["n"] == 10 and r["I"] == pytest.approx(-1.0)
    assert moran([0, 1, 0, 1, 0, 1, 0, 1, 0], line(9))["I"] is None
    assert moran([1.0] * 10, line(10))["I"] is None
