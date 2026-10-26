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


def test_worldcover_tiles_cover_the_bbox_on_the_three_degree_grid():
    from grid import worldcover_tiles

    assert worldcover_tiles((139.6, 38.8, 140.99, 40.6)) == ["N36E138", "N39E138"]  # Akita
    assert worldcover_tiles((139.6, 38.8, 141.1, 40.6)) == ["N36E138", "N36E141", "N39E138", "N39E141"]  # past 141E
    assert worldcover_tiles((134.8, 34.6, 136.1, 35.9)) == ["N33E132", "N33E135"]  # Kyoto
    assert worldcover_tiles((136.2, 36.0, 137.4, 37.9)) == ["N36E135"]  # Ishikawa: 36.0 is the tile's south edge


def test_lonlat_bbox_of_a_grid_round_trips():
    from grid import lonlat_bbox

    g = Grid(-10000.0, -10000.0, 200, 200, 100.0)  # 20 km around the origin of EPSG:6678 (40N, 140.8333E)
    b = lonlat_bbox(g, "EPSG:6678", margin_deg=0.0)
    assert b[0] < 140.8333 < b[2] and b[1] < 40.0 < b[3]
    assert 0.2 < b[2] - b[0] < 0.3 and 0.15 < b[3] - b[1] < 0.2
