"""uvx --with shapely --with pyproj --with pytest pytest test_geometry_facts.py

The behaviours that references/topology.md and references/crs-and-datum.md describe, on small shapes,
so that a library upgrade that changes them shows up here (shapely 2.2.0, pyproj 3.8.0, PROJ 9.8.1).
"""

import math

import pyproj
import pytest
import shapely
from shapely.geometry import MultiPolygon, Point, Polygon, box

SQ = box(0, 0, 1, 1)


def test_a_point_on_the_boundary_is_covered_but_not_contained():
    edge = Point(1, 0.5)
    assert not SQ.contains(edge) and not edge.within(SQ)
    assert SQ.covers(edge) and SQ.intersects(edge) and SQ.touches(edge)
    inside = Point(0.5, 0.5)
    assert SQ.contains(inside) and not SQ.touches(inside)


def test_a_centroid_can_fall_outside_its_polygon():
    c = Polygon([(0, 0), (3, 0), (3, 1), (1, 1), (1, 2), (3, 2), (3, 3), (0, 3)])     # a C
    assert not c.contains(c.centroid)
    assert c.contains(c.representative_point())
    two = MultiPolygon([box(0, 0, 1, 1), box(2, 0, 3, 1)])
    assert not two.contains(two.centroid)                                             # between the parts


def test_a_self_crossing_ring_is_invalid_and_its_area_cancels():
    bow = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bow.is_valid and bow.area == 0.0                                       # the two lobes cancel
    fixed = shapely.make_valid(bow)
    assert fixed.geom_type == "MultiPolygon" and fixed.area == pytest.approx(2.0)     # repair changes the shape


def test_ring_orientation_does_not_change_area_or_predicates_here():
    cw = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    ccw = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert not cw.exterior.is_ccw and ccw.exterior.is_ccw
    assert cw.area == ccw.area == 1.0 and cw.contains(Point(0.5, 0.5)) and ccw.contains(Point(0.5, 0.5))


def test_floating_point_puts_a_computed_edge_point_outside():
    assert 0.1 + 0.2 != 0.3
    assert not box(0, 0, 0.3, 1).covers(Point(0.1 + 0.2, 0.5))


def test_a_hairline_gap_breaks_adjacency_and_a_common_precision_restores_it():
    a, b = box(0, 0, 1, 1), box(1 + 1e-9, 0, 2, 1)
    assert not a.touches(b) and not a.intersects(b)
    assert shapely.set_precision(a, 1e-6).touches(shapely.set_precision(b, 1e-6))
    overlap = box(0.9999, 0, 2, 1)
    assert not a.touches(overlap) and a.intersects(overlap)                         # an overlap is not touching


def test_a_point_in_a_hole_is_outside():
    holed = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)], [[(1, 1), (3, 1), (3, 3), (1, 3)]])
    assert not holed.contains(Point(2, 2)) and holed.area == 12.0


def test_axis_order_of_epsg_4326_is_latitude_first():
    authority = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857")
    x, y = authority.transform(139.77, 35.68)                                        # lon, lat given in that order
    assert math.isinf(x) and math.isinf(y)                                           # read as latitude 139.77: no answer
    lonlat = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    assert lonlat.transform(139.77, 35.68)[0] == pytest.approx(15559125, abs=1)


def test_the_old_tokyo_datum_is_hundreds_of_metres_off():
    t = pyproj.Transformer.from_crs("EPSG:4301", "EPSG:6668", always_xy=True)       # Tokyo datum to JGD2011
    x, y = t.transform(139.7671, 35.6812)
    assert pyproj.Geod(ellps="GRS80").inv(139.7671, 35.6812, x, y)[2] == pytest.approx(463.5, abs=1)


def test_web_mercator_distance_is_not_ground_distance():
    geod = pyproj.Geod(ellps="WGS84").inv(139.7671, 35.6812, 135.4959, 34.7025)[2] / 1000
    t = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    (x1, y1), (x2, y2) = t.transform(139.7671, 35.6812), t.transform(135.4959, 34.7025)
    assert geod == pytest.approx(403.8, abs=0.1)
    assert math.hypot(x1 - x2, y1 - y2) / 1000 == pytest.approx(493.8, abs=0.1)   # 22 % too long at this latitude
