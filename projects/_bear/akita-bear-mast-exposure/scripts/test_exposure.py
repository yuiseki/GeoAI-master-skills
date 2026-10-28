"""Tests for burning the polygons into 10 m pixels, the 100 m counts and the disk fractions."""

import numpy as np
from shapely.geometry import box

import exposure as ex


def test_burn_is_south_up_and_counts_area():
    g = ex.Grid(x0=0.0, y0=0.0, nx=3, ny=2)  # 300 m x 200 m
    fine = ex.burn([box(0, 0, 100, 100)], g)  # the south-west cell
    cells = ex.cell_counts(fine)
    assert cells.shape == (2, 3)
    assert cells[0, 0] == 100 and cells.sum() == 100  # row 0 is the south row


def test_burn_counts_overlapping_polygons_once():
    g = ex.Grid(x0=0.0, y0=0.0, nx=1, ny=1)
    fine = ex.burn([box(0, 0, 50, 100), box(0, 0, 100, 100)], g)
    assert ex.cell_counts(fine)[0, 0] == 100


def test_disk_kernel_by_cell_centres():
    k = ex.disk(5)
    assert k.shape == (11, 11) and k[5, 5] and k[5, 0] and not k[0, 0]
    assert k.sum() == 81


def test_disk_fraction_divides_by_the_mapped_area_only():
    cat = np.zeros((5, 5))
    anyv = np.zeros((5, 5))
    anyv[:, :3] = 100  # the two eastern columns are outside the map
    cat[:, 0] = 100
    f = ex.disk_fraction(cat, anyv, 1)
    # the centre (2, 2): disk of 5 cells; mapped: (2,1),(2,2),(1,2),(3,2) = 4; category: none of them
    assert f[2, 2] == 0
    # (2, 1): disk (2,1),(2,0),(2,2),(1,1),(3,1) all mapped; category at (2,0) only
    assert np.isclose(f[2, 1], 1 / 5)
    assert np.isnan(f[2, 4])  # nothing mapped within the disk


def test_disk_sum_is_exact_for_integer_counts():
    rng = np.random.default_rng(0)
    a = rng.integers(0, 101, (40, 30)).astype(float)
    k = ex.disk(3)
    s = ex.disk_sum(a, k)
    i, j = 20, 15
    want = sum(a[i + di, j + dj] for di in range(-3, 4) for dj in range(-3, 4) if di * di + dj * dj <= 9)
    assert s[i, j] == want
