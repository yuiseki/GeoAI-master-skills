import math

import numpy as np
import pytest

import terrain as T


def test_terrarium_decode():
    # 0 m is R=128, G=0, B=0; 1 m more is G+1; B carries 1/256 m.
    rgb = np.array([[[128, 0, 0], [128, 1, 128], [127, 255, 0]]], dtype=np.uint8)
    assert T.decode_terrarium(rgb).tolist() == [[0.0, 1.5, -1.0]]


def test_pixel_of_lonlat_round_trip():
    lon, lat = 140.55, 39.77
    px, py = T.global_pixel(lon, lat, 12)
    lon2, lat2 = T.lonlat_of_global_pixel(px, py, 12)
    assert lon2 == pytest.approx(lon, abs=1e-9) and lat2 == pytest.approx(lat, abs=1e-9)
    # tile 0 of zoom 0 spans 512 px; lon 0 lat 0 is its centre
    assert T.global_pixel(0.0, 0.0, 0) == pytest.approx((256.0, 256.0))


def plane(east_slope, north_slope, n=81, step=10.0):
    """A DEM on a metric grid: z = east_slope * x + north_slope * y (x east, y north, m)."""
    c = (np.arange(n) - n // 2) * step
    x, y = np.meshgrid(c, c)
    return x.ravel(), y.ravel(), (east_slope * x + north_slope * y).ravel()


def test_plane_fit_slope_and_aspect():
    # Rising to the south (z falls toward north): the slope faces north, aspect 0, northness 1.
    x, y, z = plane(0.0, -math.tan(math.radians(20)))
    s, northness, eastness = T.slope_aspect(x, y, z)
    assert s == pytest.approx(20.0, abs=1e-6)
    assert northness == pytest.approx(1.0, abs=1e-9) and eastness == pytest.approx(0.0, abs=1e-9)
    # Falling toward east: faces east.
    x, y, z = plane(-0.1, 0.0)
    s, northness, eastness = T.slope_aspect(x, y, z)
    assert s == pytest.approx(math.degrees(math.atan(0.1)), abs=1e-6)
    assert eastness == pytest.approx(1.0, abs=1e-9) and northness == pytest.approx(0.0, abs=1e-9)


def test_flat_has_no_aspect():
    x, y, z = plane(0.0, 0.0)
    assert T.slope_aspect(x, y, z) == (0.0, 0.0, 0.0)


def test_relief_and_tpi_use_only_the_radius():
    x, y, z = plane(0.0, 0.0, n=201, step=10.0)
    z = z.copy()
    d = np.hypot(x, y)
    z[d > 300] = 1000.0  # high ground just outside 300 m
    z[(d > 0) & (d <= 50)] = -10.0
    at = 5.0
    relief, tpi = T.relief_tpi(x, y, z, at, 300.0)
    assert relief == pytest.approx(10.0)
    inside = (d <= 300)
    assert tpi == pytest.approx(at - z[inside].mean())
    relief_big, _ = T.relief_tpi(x, y, z, at, 1000.0)
    assert relief_big == pytest.approx(1010.0)
