import numpy as np
import shapely
from shapely.geometry import LineString

import feat_osm as fo
from grid import Grid


def test_line_presence_marks_every_cell_a_straight_line_crosses():
    g = Grid(0, 0, 10, 3, 100)
    pres = fo.line_presence(g, [LineString([(5, 150), (995, 150)])], step=20)
    assert pres[1].all() and not pres[0].any() and not pres[2].any()


def test_line_presence_does_not_skip_cells_on_a_long_diagonal_segment():
    g = Grid(0, 0, 10, 10, 100)
    pres = fo.line_presence(g, [LineString([(5, 5), (995, 995)])], step=20)
    assert all(pres[i, i] for i in range(10))


def test_distance_is_zero_on_the_feature_and_in_metres_elsewhere():
    pres = np.zeros((5, 5), dtype=bool)
    pres[2, 2] = True
    d = fo.distance_m(pres, 100.0)
    assert d[2, 2] == 0 and d[2, 4] == 200 and np.isclose(d[0, 0], np.hypot(200, 200))


def test_distance_without_any_feature_is_nan_not_zero():
    d = fo.distance_m(np.zeros((3, 3), dtype=bool), 100.0)
    assert np.isnan(d).all()


def test_padded_grid_shares_cell_edges_and_crops_back():
    g = Grid(1000, 2000, 4, 3, 100)
    p, off = fo.padded(g, 2)
    assert p.x0 == 800 and p.y0 == 1800 and p.nx == 8 and p.ny == 7 and off == 2
    arr = np.arange(p.nx * p.ny).reshape(p.ny, p.nx)
    assert fo.crop(arr, off, g).shape == (3, 4)
    assert fo.crop(arr, off, g)[0, 0] == arr[2, 2]
