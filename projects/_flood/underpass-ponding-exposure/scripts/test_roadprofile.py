import math

import numpy as np
from shapely.geometry import LineString, Point

from roadprofile import (ambiguous, build_chain, depth, eligible, layer_value, lonlat_to_merc, merc_to_lonlat, samples,
                     surface_depth)


def test_layer_value():
    assert layer_value(None) is None and layer_value("-1") == -1 and layer_value("0;1") == 0 and layer_value("x") is None


def test_eligible():
    assert eligible("residential", None, None)
    assert eligible("primary", "no", "-1")
    assert not eligible("primary", "yes", None)
    assert not eligible("primary", "viaduct", None)
    assert not eligible("primary", None, "1")
    assert not eligible("footway", None, None)


def test_depth_v_shape():
    s = np.arange(-100, 100.1, 2.5)
    e = np.abs(s) / 10  # bottom 0 at s = 0, 10 m at both ends
    d, sb, ok = depth(s, e, 100)
    assert ok and abs(d - 10) < 1e-9 and sb == 0
    d, sb, ok = depth(s, e, 50)
    assert ok and abs(d - 5) < 1e-9


def test_depth_sill_is_lower_side():
    s = np.arange(-100, 100.1, 2.5)
    e = np.where(s < 0, -s / 20, s / 10)  # left rises to 5, right to 10
    d, _, ok = depth(s, e, 100)
    assert ok and abs(d - 5) < 1e-9


def test_depth_bottom_only_near_point():
    s = np.arange(-100, 100.1, 2.5)
    e = np.zeros_like(s)
    e[s == 80] = -5  # a low spot far from the point is not the bottom
    d, sb, ok = depth(s, e, 100)
    assert ok and d == 0 and abs(sb) <= 30


def test_depth_not_measurable():
    s = np.arange(-100, 100.1, 2.5)
    e = np.zeros_like(s)
    e[:30] = np.nan
    assert depth(s, e, 100)[2] is False
    assert depth(np.arange(-20, 100.1, 2.5), np.zeros(49), 100)[2] is False  # short on one side


def test_surface_depth():
    win = np.full((41, 41), 10.0)
    win[20, 20] = 7.0
    assert surface_depth(win, 2.0, 20, 20) == 3.0


def test_mercator_round_trip():
    x, y = lonlat_to_merc(139.77, 35.68)
    lon, lat = merc_to_lonlat(x, y)
    assert abs(lon - 139.77) < 1e-9 and abs(lat - 35.68) < 1e-9


def _ends(lines):
    ends = {}
    for i, ln in enumerate(lines):
        for c in (ln.coords[0], ln.coords[-1]):
            ends.setdefault(tuple(c), []).append(i)
    return ends


def test_build_chain_follows_straight_not_turn():
    lines = [LineString([(0, 0), (100, 0)]),
             LineString([(100, 0), (200, 0)]),     # straight on
             LineString([(100, 0), (100, 100)]),   # 90 degree turn
             LineString([(-100, 0), (0, 0)])]      # behind
    chain, used = build_chain(0, lines, _ends(lines), 150)
    assert set(used) == {0, 1, 3}
    assert chain.length == 300


def test_samples_and_sides():
    chain = LineString([(0, 0), (400, 0)])
    pts, left, right = samples(chain, Point(100, 5), 1.0, 200)
    assert left == 100 and right == 300
    assert pts[0][0] == -100 and pts[-1][0] == 200


def test_ambiguous_crossing():
    lines = [LineString([(-50, 0), (50, 0)]), LineString([(0, -50), (0, 50)])]
    assert ambiguous(Point(1, 1), lines, 0, 1.0)
    lines = [LineString([(-50, 0), (50, 0)]), LineString([(-50, 3), (50, 3)])]
    assert not ambiguous(Point(1, 1), lines, 0, 1.0)
