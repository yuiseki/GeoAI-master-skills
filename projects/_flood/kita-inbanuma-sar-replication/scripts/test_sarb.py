# uvx --with pytest --with numpy --with scipy pytest scripts/test_sarb.py -q
import math

import numpy as np
import pytest

from sarb import (Geolocation, azimuth_noise, colour_to_depth, depth_from_surfaces, extrapolate, legend_table, parts,
                  shift_by_correlation, sigma0, surface_iou, surface_quantile, tile_pixel_lonlat, to_grid_mean,
                  vectors_to_grid)


def ramp_image():
    """A legend bar of 101 rows from white (0 m) to blue (10 m) on a black, transparent background."""
    rgb = np.zeros((121, 40, 3), np.uint8)
    alpha = np.zeros((121, 40), np.uint8)
    t = np.linspace(0, 1, 101)[:, None]
    rgb[10:111, 10:30] = (np.column_stack([255 * (1 - t), 255 * (1 - t), 255 - 100 * t])[:, None, :]).astype(np.uint8)
    alpha[10:111, 10:30] = 255
    return rgb, alpha


def test_legend_table_reads_the_bar_top_to_bottom():
    d, c = legend_table(*ramp_image())
    assert len(d) == 101 and d[0] == 0 and d[-1] == 10
    assert tuple(c[0]) == (255, 255, 255) and tuple(c[-1]) == (0, 0, 155)


def test_legend_table_ignores_a_black_shadow_in_the_mask():
    rgb, alpha = ramp_image()
    alpha[:, :] = 0
    alpha[2:119, 2:38] = 255  # the mask covers a black margin around the bar
    d, c = legend_table(rgb, alpha)
    assert len(d) == 101 and tuple(c[0]) == (255, 255, 255)


def test_colour_to_depth_nearest_and_far_and_transparent():
    d, c = legend_table(*ramp_image())
    px = np.array([[[255, 255, 255, 255], [127, 127, 205, 255], [255, 0, 0, 255], [0, 0, 0, 0]]], np.uint8)
    depth, n_far = colour_to_depth(px, d, c)
    assert depth[0, 0] == 0 and depth[0, 1] == pytest.approx(5.0, abs=0.11)
    assert np.isnan(depth[0, 2]) and np.isnan(depth[0, 3]) and n_far == 1


def test_tile_pixel_lonlat_corners():
    lon, lat = tile_pixel_lonlat(0, 0, 0, (256, 256))
    assert lon[0, 0] == pytest.approx(-180 + 360 / 512)
    assert lat[128, 0] == pytest.approx(-lat[127, 0])


def test_to_grid_mean_cover_rule():
    # a 2 x 1 grid of 10 m cells; 4 points in each cell
    x = np.array([1, 2, 3, 4, 11, 12, 13, 14], float)
    y = np.full(8, -5.0)
    v = np.array([1, 2, 3, np.nan, 5, np.nan, np.nan, np.nan])
    g = to_grid_mean(v, x, y, (10, 0, 0, 0, -10, 0), (1, 2))
    assert g[0, 0] == 2.0 and np.isnan(g[0, 1])


def test_vectors_to_grid_bilinear():
    out = vectors_to_grid([0, 10], [[0, 10], [0, 20]], [[0, 10], [100, 120]], np.array([0, 5, 10]), np.array([0, 10]))
    assert out[0].tolist() == [0, 10] and out[2].tolist() == [100, 110]
    assert out[1].tolist() == [50, 60]


def test_azimuth_noise_blocks():
    blocks = [(0, 9, 0, 4, [0, 9], [1.0, 2.0]), (0, 9, 5, 9, [0, 9], [3.0, 3.0])]
    out = azimuth_noise(blocks, np.array([0, 9]), np.array([0, 5, 20]))
    assert out.tolist() == [[1, 3, 1], [2, 3, 1]]


def test_sigma0_removes_noise_and_floors():
    s = sigma0(np.array([10, 1]), np.array([10.0, 10.0]), np.array([36.0, 4.0]))
    assert s[0] == pytest.approx(0.64) and s[1] == 1e-5


def geometry(h_scale=1.0):
    """A synthetic ascending, right-looking geometry: line grows to the north, pixel to the east (10 m spacing),
    incidence 30 to 45 degrees across. A ground point (x, y, h) is seen at pixel = x / 10 - h / (tan(inc) * 10)."""
    lon0, lat0 = 140.0, 35.8
    m_lon = 111320 * math.cos(math.radians(lat0))

    def truth(lon, lat, h):
        x, y = (lon - lon0) * m_lon, (lat - lat0) * 111320
        inc = 30 + 15 * x / 50000
        return y / 10, x / 10 - h / (np.tan(np.radians(inc)) * 10), inc
    lons, lats = np.meshgrid(np.linspace(lon0, lon0 + 50000 / m_lon, 10), np.linspace(lat0, lat0 + 0.3, 21))
    hs = h_scale * 300 * np.sin(lons * 50) ** 2
    line, pix, inc = truth(lons, lats, hs)
    return Geolocation(line.ravel(), pix.ravel(), lons.ravel(), lats.ravel(), hs.ravel(), inc.ravel(), 10.0), truth


def test_geolocation_recovers_line_and_height_shift():
    geo, truth = geometry()
    lon, lat = np.array([140.2, 140.3]), np.array([35.9, 35.95])
    for h in (0.0, 40.0):
        line, pix, _ = geo(lon, lat, np.full(2, h))
        tl, tp, _ = truth(lon, lat, h)
        assert np.abs(line - tl).max() < 0.05 and np.abs(pix - tp).max() < 0.05


def test_geolocation_height_moves_towards_near_range():
    geo, _ = geometry()
    _, p0, inc = geo(np.array([140.2]), np.array([35.9]), np.array([0.0]))
    _, p40, _ = geo(np.array([140.2]), np.array([35.9]), np.array([40.0]))
    assert p40[0] - p0[0] == pytest.approx(-40 / (math.tan(math.radians(inc[0])) * 10), rel=1e-3)


def test_shift_by_correlation_finds_a_known_shift():
    rng = np.random.default_rng(0)
    base = ndimage_smooth(rng.normal(size=(80, 80)))
    a = base[10:70, 10:70]
    b = base[12:72, 7:67]  # a[i] = b[i + (-2, 3)]
    dr, dc, score = shift_by_correlation(a, b)
    assert dr == pytest.approx(-2, abs=0.2) and dc == pytest.approx(3, abs=0.2) and score > 0.9


def ndimage_smooth(x):
    from scipy import ndimage
    return ndimage.gaussian_filter(x, 2)


def test_surface_quantile_and_depth():
    dem = np.array([[0.0, 1.0, 2.0, 9.0]])
    part = np.array([[True, True, True, False]])
    s = surface_quantile(part, dem, q=1.0)
    assert s == 2.0
    d = depth_from_surfaces(part.astype(int), {1: s}, dem)
    assert d[0, :3].tolist() == [2.0, 1.0, 0.0] and np.isnan(d[0, 3])


def test_surface_iou_finds_the_level_that_matches_the_water():
    dem = np.tile(np.arange(0, 3, 0.1), (5, 1))  # rises to the east, 30 columns
    water = dem < 1.5
    s, iou = surface_iou(water, water, dem)
    # candidates stop at the 99 % point of the ground in the part (just under 1.4), so the top column is left out
    assert 1.3 < s <= 1.4 and iou > 0.9


def test_surface_iou_with_mud_reads_high():
    dem = np.tile(np.arange(0, 3, 0.1), (5, 1))
    water = dem < 1.95  # water up to 1.5 plus wet mud up to 1.9 classed as water
    s, _ = surface_iou(water, water, dem)
    assert s > 1.8


def test_parts_and_extrapolate():
    m = np.zeros((4, 4), bool)
    m[0, 0] = True
    m[2:4, 2:4] = True
    assert parts(m, 2).max() == 1
    assert extrapolate(0, 2.0, 1, 1.0, 3) == pytest.approx(-1.0)


def test_surfaces_of_a_part_without_ground_are_nan():
    part = np.array([[True, True]])
    dem = np.full((1, 2), np.nan)
    assert np.isnan(surface_quantile(part, dem)) and np.isnan(surface_iou(part, part, dem)[0])
