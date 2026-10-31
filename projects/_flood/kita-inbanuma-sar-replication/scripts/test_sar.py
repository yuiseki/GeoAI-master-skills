# uvx --with pytest --with numpy --with scipy --with shapely pytest scripts/test_sar.py -q
import numpy as np
import pytest
from shapely.geometry import box

from sar import buffer_for_area, components, detect, edge_quantile, floodable, gauss_posterior, metrics, to_db


def test_to_db():
    out = to_db([1.0, 0.1, 0.0, -1.0, np.nan])
    assert out[0] == 0 and out[1] == pytest.approx(-10)
    assert np.isnan(out[2:]).all()


def test_posterior_equal_spread_crosses_at_midpoint():
    p = gauss_posterior(np.array([-22.0, -15.0, -8.0]), -22, 2, -8, 2)
    assert p[0] > 0.99 and p[1] == pytest.approx(0.5) and p[2] < 0.01


def test_posterior_wider_land_takes_far_tail():
    # a value far below the narrow water spread is more likely land when land is wide
    p = gauss_posterior(np.array([-40.0]), -22, 1, -8, 6)
    assert p[0] < 0.5


def test_components_drops_small_and_diagonal_is_not_joined():
    m = np.zeros((5, 5), bool)
    m[0, 0] = m[1, 1] = True  # diagonal only: two parts of 1
    m[3:5, 2:5] = True        # one part of 6
    lab = components(m, 2)
    assert lab.max() == 1 and (lab == 1).sum() == 6 and lab[0, 0] == 0


def test_edge_quantile_uses_border_pixels_only():
    lab = np.zeros((5, 5), int)
    lab[1:4, 1:4] = 1
    dem = np.full((5, 5), 9.0)
    dem[1:4, 1:4] = 1.0
    dem[2, 2] = -100.0  # the centre is not an edge pixel, so it cannot be the minimum
    assert edge_quantile(lab, dem, q=0.0)[1] == 1.0


def test_edge_quantile_skips_nan_and_gives_nan_when_empty():
    lab = np.array([[1, 1], [0, 0]])
    dem = np.array([[np.nan, 3.0], [0, 0]])
    assert edge_quantile(lab, dem)[1] == 3.0
    assert np.isnan(edge_quantile(lab, np.full((2, 2), np.nan))[1])


def test_floodable_stops_at_a_levee_and_crosses_water():
    dem = np.array([[1, 1, 5, 1, 1, 1],
                    [1, 1, 5, 1, 9, 1]], float)
    lab = np.zeros(dem.shape, int)
    lab[0, 0] = 1
    passable = np.zeros(dem.shape, bool)
    f = floodable(lab, {1: 2.0}, dem, passable)
    assert f[:, :2].all() and not f[:, 2:].any()
    passable[:, 2] = True  # a water body through the levee
    f = floodable(lab, {1: 2.0}, dem, passable)
    assert f[0, 5] and not f[1, 4]


def test_floodable_nan_level_keeps_only_the_part():
    lab = np.array([[1, 0]])
    f = floodable(lab, {1: np.nan}, np.zeros((1, 2)), np.zeros((1, 2), bool))
    assert f.tolist() == [[True, False]]


def test_metrics():
    ref = np.array([1, 1, 1, 1, 0, 0], bool)
    det = np.array([1, 1, 0, 0, 1, 0], bool)
    valid = np.array([1, 1, 1, 1, 1, 0], bool)
    m = metrics(ref, det, valid)
    assert m["ref_m2"] == 400 and m["det_m2"] == 300 and m["both_m2"] == 200
    assert m["missed_m2"] == 200 and m["extra_m2"] == 100
    assert m["recall"] == 0.5 and m["precision"] == pytest.approx(2 / 3)


def test_buffer_for_area():
    g = box(0, 0, 10, 10)
    d = buffer_for_area(g, 400.0)
    assert g.buffer(d).area == pytest.approx(400.0, abs=0.5)
    with pytest.raises(ValueError):
        buffer_for_area(g, 50.0)


def scene(seed=0):
    """A 60 x 60 scene: a lake (west), a flat polder at 1 m, flooded deep in the centre and shallowly (rice above the
    water) in a strip at its east side,
    a levee at 6 m between the polder and a dry low field at 1 m (east, not flooded), and high land at 20 m (south)
    where one field darkens in VH (tilled), which must not be called flood."""
    rng = np.random.default_rng(seed)
    n = 60
    dem = np.full((n, n), 1.0)
    water = np.zeros((n, n), bool)
    water[:40, :10] = True
    dem[:40, :10] = 0.0
    dem[:40, 30:33] = 6.0           # levee
    dem[40:, :] = 20.0              # high land
    vv_b = np.full((n, n), -8.0)
    vh_b = np.full((n, n), -14.0)
    vv_b[water] = -22
    vh_b[water] = -28
    vv_a, vh_a = vv_b.copy(), vh_b.copy()
    vv_a[:40, 10:25] = -21          # deep flood in the polder
    vh_a[:40, 10:25] = -27
    vv_a[:40, 25:30] = -10.5        # shallow: little VV change, VH darkens
    vh_a[:40, 25:30] = -19
    vh_a[45:48, 40:43] = -19        # tilled field on high land (9 pixels, under 1 % of the high land)
    noise = lambda: rng.normal(0, 0.5, (n, n))
    return vv_b + noise(), vh_b + noise(), vv_a + noise(), vh_a + noise(), dem, water


def test_detect_finds_deep_flood_and_vh_adds_shallow_only_inside_the_zone():
    vv_b, vh_b, vv_a, vh_a, dem, water = scene()
    r = detect(vv_b, vh_b, vv_a, vh_a, dem, water, min_size=20)
    deep = np.zeros(dem.shape, bool)
    deep[:40, 10:25] = True
    shallow = np.zeros(dem.shape, bool)
    shallow[:40, 25:30] = True
    assert r["det_vv"][deep].mean() > 0.95
    assert r["det_vv"][shallow].mean() < 0.2
    assert r["det_vvvh"][shallow].mean() > 0.9
    assert not r["det_vvvh"][40:, :].any()       # the tilled field on high land
    assert not r["det_vvvh"][:40, 33:].any()     # behind the levee
    assert not r["det_vvvh"][water].any()


def test_detect_without_the_zone_lets_the_tilled_field_in():
    vv_b, vh_b, vv_a, vh_a, dem, water = scene()
    r = detect(vv_b, vh_b, vv_a, vh_a, dem, water, min_size=20, use_floodable=False)
    assert r["det_vvvh"][45:48, 40:43].all()


def test_detect_level_from_the_edge_is_low_when_the_shallow_margin_is_missed():
    # a polder whose ground rises to the east: water at 2.5 m; VV sees only depth over 0.5 m (ground under 2.0 m),
    # the margin between 2.0 and 2.5 m darkens only in VH. The edge of the sure water sits near 2.0 m, so the
    # level is too low and the VH pixels of the margin stay outside the zone (the bias article 2 describes).
    vv_b, vh_b, vv_a, vh_a, dem, water = scene()
    ramp = np.linspace(0.5, 3.0, 20)
    dem[:40, 10:30] = ramp
    deep = np.zeros(dem.shape, bool)
    deep[:40, 10:30] = dem[:40, 10:30] < 2.0
    margin = np.zeros(dem.shape, bool)
    margin[:40, 10:30] = (dem[:40, 10:30] >= 2.0) & (dem[:40, 10:30] < 2.5)
    rng = np.random.default_rng(1)
    vv_a[:40, 10:30] = -8 + rng.normal(0, 0.5, (40, 20))
    vh_a[:40, 10:30] = -14 + rng.normal(0, 0.5, (40, 20))
    vv_a[deep], vh_a[deep] = -21, -27
    vv_a[margin], vh_a[margin] = -10.5, -19
    r = detect(vv_b, vh_b, vv_a, vh_a, dem, water, min_size=20)
    assert r["levels"][1] < 2.0
    assert r["det_vvvh"][margin].mean() < 0.1
