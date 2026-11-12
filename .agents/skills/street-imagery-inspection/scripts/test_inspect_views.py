"""uvx --with numpy --with scipy --with pytest pytest test_inspect_views.py"""

# Tests for inspect_views.py without the detector: which boxes count as poles, duplicate boxes, the vegetation
# share by the excess-green index, the distance to a pole's foot, the point it gives, and merging the same pole
# seen from several pictures.

import math

import numpy as np
import pytest

from inspect_views import (destination, exg_mask, foot_distance, merge_points, nms, pole_like, vegetation_share)


def test_pole_like_keeps_tall_thin_boxes():
    assert pole_like((100, 50, 120, 400), view_h=1000)               # 20 x 350
    assert not pole_like((100, 50, 300, 400), view_h=1000)           # wide
    assert not pole_like((100, 350, 110, 400), view_h=1000)          # short


def test_nms_drops_the_weaker_overlapping_box():
    boxes = [(0, 0, 10, 100), (1, 2, 11, 101), (50, 0, 60, 100)]
    keep = nms(boxes, [0.9, 0.5, 0.7], iou=0.5)
    assert keep == [0, 2]


def test_exg_marks_green_not_grey():
    img = np.zeros((10, 10, 3), np.uint8)
    img[:5] = (40, 140, 40)            # leaves
    img[5:] = (120, 120, 120)          # road
    m = exg_mask(img)
    assert m[:5].all() and not m[5:].any()


def test_vegetation_share_around_the_top_of_a_pole():
    img = np.full((400, 400, 3), 120, np.uint8)
    img[0:120, 150:260] = (40, 140, 40)                 # a tree crown near the top of the pole
    share = vegetation_share(img, (195, 40, 205, 380))
    assert share > 0.5
    img2 = np.full((400, 400, 3), 120, np.uint8)
    assert vegetation_share(img2, (195, 40, 205, 380)) == 0


def test_foot_distance_from_the_depression_angle():
    # A level view 1000 px high with a 90-degree field: f = 500 px. A foot 100 px below the centre is atan(0.2)
    # below the horizon; from 2.5 m up that is 2.5 / 0.2 = 12.5 m away.
    d = foot_distance(y_foot=599.5 + 100, view_h=1200, view_w=1000, fov=90, camera_height=2.5)
    assert d == pytest.approx(12.5, rel=1e-6)
    assert foot_distance(y_foot=500, view_h=1200, view_w=1000, fov=90, camera_height=2.5) is None   # above horizon


def test_destination_moves_north_and_east():
    lat, lon = destination(45.0, 0.0, 0.0, 111.2)
    assert lat == pytest.approx(45.001, abs=2e-5) and lon == pytest.approx(0.0)
    lat, lon = destination(45.0, 0.0, 90.0, 100.0)
    assert lon == pytest.approx(100 / (111195 * math.cos(math.radians(45))), rel=1e-3)


def test_merge_points_joins_sightings_within_the_radius():
    pts = [(44.85, -0.70), (44.85001, -0.70001), (44.86, -0.70)]
    labels = merge_points(pts, radius_m=5)
    assert labels[0] == labels[1] != labels[2]
