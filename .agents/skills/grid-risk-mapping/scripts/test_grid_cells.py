"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with pandas --with pyarrow --with pytest pytest test_grid_cells.py

Expected values are worked out by hand on grids of a few cells.
"""

import numpy as np
import pytest
from shapely.geometry import box

import grid_cells as gc


def test_index_floors_to_the_cell_and_marks_points_off_the_grid():
    g = gc.Grid(1000.0, 2000.0, 3, 2, 100.0)
    ix, iy, ok = g.index(np.array([1000.0, 1099.9, 1100.0, 1299.9, 999.9, 1300.0]), np.array([2000.0] * 6))
    assert list(ix[ok]) == [0, 0, 1, 2] and list(ok) == [True, True, True, True, False, False]


def test_from_bounds_keeps_a_bound_on_a_cell_edge():
    g = gc.Grid.from_bounds(1234.0, 5678.0, 1501.0, 5900.0, size=100.0)
    assert (g.x0, g.y0, g.nx, g.ny) == (1200.0, 5600.0, 4, 4)
    assert g.index(np.array([1501.0]), np.array([5900.0]))[2].all()


def test_sum_into_keeps_the_total_off_the_grid():
    g = gc.Grid(0.0, 0.0, 2, 2, 100.0)
    arr, off = g.sum_into(np.array([10.0, 20.0, 150.0, 500.0]), np.array([10.0, 20.0, 150.0, 500.0]), np.array([1.0, 2.0, 4.0, 8.0]))
    assert arr[0, 0] == 3 and arr[1, 1] == 4 and off == 8


def test_cells_inside_go_by_the_centre_and_the_first_polygon():
    g = gc.Grid(0.0, 0.0, 10, 5, 100.0)
    lab = gc.cells_inside(g, [box(0, 0, 500, 500), box(500, 0, 1000, 500)])
    assert (lab[:, :5] == 0).all() and (lab[:, 5:] == 1).all()
    lab = gc.cells_inside(g, [box(0, 0, 140, 140)])  # covers part of 4 cells but only one centre
    assert (lab == 0).sum() == 1


def test_box_sum_and_box_mean():
    a = np.zeros((7, 7))
    a[3, 3] = 1.0
    s = gc.box_sum(a, 1)
    assert s[3, 3] == 1 and s[2, 2] == 1 and s[1, 1] == 0
    assert gc.box_sum(np.ones((3, 3)), 1)[0, 0] == 4  # outside the grid counts as 0
    assert np.isclose(gc.box_mean(np.array([[1.0, np.nan], [3.0, 5.0]]), 1)[0, 0], 3.0)
    assert np.isnan(gc.box_mean(np.full((2, 2), np.nan), 1)).all()


def test_box_sum_matches_a_brute_force_loop():
    rng = np.random.default_rng(0)
    a = rng.random((9, 11))
    r = 2
    s = gc.box_sum(a, r)
    for i in range(9):
        for j in range(11):
            assert np.isclose(s[i, j], a[max(0, i - r):i + r + 1, max(0, j - r):j + r + 1].sum())


def test_history_reads_only_the_periods_before_the_target():
    rng = np.random.default_rng(0)
    counts = {p: rng.poisson(0.2, size=(20, 20)).astype(float) for p in (2022, 2023, 2024, 2025)}
    h1 = gc.period_history(counts, 2024, {"cell": 0, "r2": 2}, 100.0)
    changed = dict(counts)
    changed[2024] = counts[2024] + 50
    changed[2025] = counts[2025] + 99
    h2 = gc.period_history(changed, 2024, {"cell": 0, "r2": 2}, 100.0)
    for k in h1:
        np.testing.assert_array_equal(np.nan_to_num(h1[k], nan=-1), np.nan_to_num(h2[k], nan=-1), err_msg=k)


def test_history_is_a_share_of_the_period_total():
    a = np.zeros((10, 10))
    a[5, 5], a[1, 1] = 2, 1
    small = gc.period_history({1: a, 2: a}, 2, {"r1": 1}, 100.0)
    big = gc.period_history({1: a * 10, 2: a}, 2, {"r1": 1}, 100.0)
    np.testing.assert_allclose(small["h_last_r1"], big["h_last_r1"])
    a2 = np.zeros((5, 5))
    a2[0, 0] = 1
    h = gc.period_history({1: a2, 2: np.zeros((5, 5))}, 2, {}, 100.0)
    assert h["h_dist"][0, 0] == 0 and h["h_dist"][0, 3] == 300
    with pytest.raises(ValueError):
        gc.period_history({2: a2}, 2, {}, 100.0)
