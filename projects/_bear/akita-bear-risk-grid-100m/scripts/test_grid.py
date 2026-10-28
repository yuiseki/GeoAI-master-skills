"""Tests for grid.py: the 100 m grid in EPSG:6678, cell indices, and summing values into cells."""

import numpy as np
import pytest

from grid import Grid


def test_index_floors_to_the_cell_and_marks_points_outside():
    g = Grid(x0=1000.0, y0=2000.0, nx=3, ny=2, size=100.0)
    ix, iy, ok = g.index(np.array([1000.0, 1099.9, 1100.0, 1299.9, 999.9, 1300.0]), np.array([2000.0] * 6))
    assert list(ix[ok]) == [0, 0, 1, 2]
    assert list(ok) == [True, True, True, True, False, False]
    ix, iy, ok = g.index(np.array([1050.0, 1050.0, 1050.0]), np.array([2000.0, 2199.9, 2200.0]))
    assert list(iy[ok]) == [0, 1] and list(ok) == [True, True, False]


def test_centres_are_half_a_cell_in():
    g = Grid(x0=0.0, y0=0.0, nx=2, ny=2, size=100.0)
    x, y = g.centres()
    assert x.shape == (2, 2)
    assert x[0, 0] == 50.0 and x[0, 1] == 150.0 and y[0, 0] == 50.0 and y[1, 0] == 150.0


def test_sum_into_cells_conserves_the_total_inside_and_reports_outside():
    g = Grid(x0=0.0, y0=0.0, nx=2, ny=2, size=100.0)
    x = np.array([10.0, 20.0, 150.0, 500.0])
    y = np.array([10.0, 20.0, 150.0, 500.0])
    v = np.array([1.0, 2.0, 4.0, 8.0])
    arr, outside = g.sum_into(x, y, v)
    assert arr[0, 0] == 3.0 and arr[1, 1] == 4.0 and arr.sum() == 7.0
    assert outside == 8.0


def test_from_bounds_covers_the_bounds_on_whole_cells():
    g = Grid.from_bounds(1234.0, 5678.0, 1501.0, 5900.0, size=100.0)
    assert g.x0 == 1200.0 and g.y0 == 5600.0
    assert g.nx == 4 and g.ny == 4
    # the bounds themselves fall on the grid, even when a bound is exactly on a cell edge (5900)
    _, _, ok = g.index(np.array([1234.0, 1501.0]), np.array([5678.0, 5900.0]))
    assert ok.all()
