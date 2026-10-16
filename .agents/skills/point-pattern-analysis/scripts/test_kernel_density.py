"""uvx --with numpy --with scipy --with pytest pytest test_kernel_density.py"""

import numpy as np
import pytest

from kernel_density import edge_mass, intensity, lcv_bandwidth, local_maxima


def _grid(lo, hi, cell):
    c = np.arange(lo + cell / 2, hi, cell)
    gx, gy = np.meshgrid(c, c)
    return gx.ravel(), gy.ravel(), len(c)


def test_intensity_integrates_to_the_number_of_points_in_a_wide_window():
    rng = np.random.default_rng(0)
    x, y = rng.normal(0, 2, 100), rng.normal(0, 2, 100)
    gx, gy, m = _grid(-30, 30, 0.5)
    lam = intensity(x, y, gx, gy, h=1.5)
    assert (lam * 0.25).sum() == pytest.approx(100, rel=0.01)


def test_edge_correction_lifts_the_corners_back_to_the_interior_level():
    # Uniform points in a 20 x 20 square: without correction the corner intensity is about a quarter of the
    # middle's; divided by the kernel mass inside the window, it comes back.
    rng = np.random.default_rng(1)
    x, y = rng.uniform(0, 20, 4000), rng.uniform(0, 20, 4000)
    gx, gy, m = _grid(0, 20, 0.5)
    raw = intensity(x, y, gx, gy, h=2.0).reshape(m, m)
    mass = edge_mass(gx, gy, 2.0, (0, 20, 0, 20)).reshape(m, m)
    corr = raw / mass
    middle = raw[15:25, 15:25].mean()
    assert raw[0, 0] < 0.4 * middle
    assert corr[0, 0] == pytest.approx(middle, rel=0.2)
    assert mass[20, 20] == pytest.approx(1.0, abs=0.01)


def test_likelihood_cross_validation_picks_a_bandwidth_near_the_cluster_scale():
    rng = np.random.default_rng(2)
    x, y = rng.normal(0, 1.0, 300), rng.normal(0, 1.0, 300)
    h = lcv_bandwidth(x, y, np.geomspace(0.05, 3, 25))["h"]
    assert 0.2 < h < 0.8  # about sd n^(-1/6) = 0.39 for a Gaussian


def test_a_wider_bandwidth_merges_peaks():
    rng = np.random.default_rng(3)
    centres = rng.uniform(0, 30, (6, 2))
    k = rng.integers(0, 6, 600)
    x, y = centres[k, 0] + rng.normal(0, 0.8, 600), centres[k, 1] + rng.normal(0, 0.8, 600)
    gx, gy, m = _grid(-5, 35, 0.5)
    narrow = local_maxima(intensity(x, y, gx, gy, h=0.8).reshape(m, m))
    wide = local_maxima(intensity(x, y, gx, gy, h=6.0).reshape(m, m))
    assert wide < narrow
    assert wide <= 3


def test_great_circle_distances_at_high_latitude():
    # Two points 1 degree of longitude apart at 60 N are about 55.6 km apart: with h 20 km the kernel at one point
    # from the other is exp(-(55.6/20)^2 / 2).
    lam = intensity(np.array([0.0]), np.array([60.0]), np.array([1.0]), np.array([60.0]), h=20.0, lonlat=True)
    assert lam[0] == pytest.approx(np.exp(-0.5 * (55.6 / 20) ** 2) / (2 * np.pi * 400), rel=0.02)
