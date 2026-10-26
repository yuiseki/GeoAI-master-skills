"""Tests for rasteragg: pixel centres, and putting pixel values into grid cells by their kind."""

import numpy as np
from affine import Affine

import rasteragg as ra
from grid import Grid


def test_pixel_centres_follow_the_affine_transform():
    t = Affine(0.5, 0, 100.0, 0, -0.5, 50.0)  # 0.5 units, north-up, top-left (100, 50)
    lon, lat = ra.pixel_centres(t, row0=2, nrows=2, col0=1, ncols=3)
    assert lon.shape == (2, 3)
    assert lon[0, 0] == 100.75 and lat[0, 0] == 48.75 and lon[0, 2] == 101.75 and lat[1, 0] == 48.25


def test_classes_are_counted_per_cell_and_nodata_and_outside_are_kept_apart():
    g = Grid(0, 0, 2, 1, 100)
    acc = ra.ClassAcc(g, classes=[10, 40])
    x = np.array([10, 20, 30, 150, 160, 999])
    y = np.array([10, 10, 10, 10, 10, 10])
    v = np.array([10, 10, 40, 40, 0, 10])  # 0 is NoData; the last pixel is off the grid
    acc.add(v, x, y, nodata=0)
    assert acc.counts[10][0, 0] == 2 and acc.counts[40][0, 0] == 1 and acc.counts[40][0, 1] == 1
    assert acc.nodata[0, 1] == 1 and acc.outside == 1
    frac = acc.fractions()
    assert frac[10][0, 0] == 2 / 3 and frac[40][0, 1] == 1.0


def test_sum_conserves_the_total_and_counts_nodata_separately():
    g = Grid(0, 0, 2, 1, 100)
    acc = ra.SumAcc(g)
    acc.add(np.array([1.5, 2.0, -99999.0, 4.0]), np.array([10, 150, 150, 500]), np.array([10, 10, 10, 10]), nodata=-99999.0)
    assert acc.total[0, 0] == 1.5 and acc.total[0, 1] == 2.0
    assert acc.outside == 4.0 and acc.nodata[0, 1] == 1


def test_mean_is_over_valid_pixels_only():
    g = Grid(0, 0, 1, 1, 100)
    acc = ra.MeanAcc(g)
    acc.add(np.array([100.0, 200.0, np.nan]), np.array([10, 20, 30]), np.array([10, 10, 10]), nodata=None)
    assert acc.mean()[0, 0] == 150.0 and acc.nodata[0, 0] == 1
    empty = ra.MeanAcc(Grid(0, 0, 2, 1, 100))
    assert np.isnan(empty.mean()).all()  # no pixel: NaN, not 0
