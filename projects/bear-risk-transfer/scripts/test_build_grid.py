import numpy as np
from shapely.geometry import box

from build_grid import cells_inside
from grid import Grid


def test_cells_inside_uses_cell_centres_and_labels_each_cell_by_its_polygon():
    g = Grid(0.0, 0.0, 10, 5, 100.0)
    polys = [box(0, 0, 500, 500), box(500, 0, 1000, 500)]  # two halves
    muni = cells_inside(g, polys)
    assert muni.shape == (5, 10)
    assert (muni[:, :5] == 0).all() and (muni[:, 5:] == 1).all()
    # a polygon that only touches part of a cell, short of its centre, does not take it
    muni = cells_inside(g, [box(0, 0, 140, 140)])
    assert (muni == 0).sum() == 1 and (muni == -1).sum() == 49
