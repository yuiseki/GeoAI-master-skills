"""uvx --with numpy --with pillow --with pytest pytest test_equirect_view.py"""

# Tests for equirect_view.py: a perspective view cut from a 360-degree equirectangular image. A world-vertical
# line must stay vertical in a level view, a line at a known heading must land at the centre of a view turned to
# that heading, and the pitch must move the horizon by the right number of pixels.

import math

import numpy as np
import pytest

from equirect_view import heading_of_column, perspective


def equirect_with_meridian(w=2048, h=1024, lon_deg=30.0):
    """A white image with a black meridian (a vertical world line) at lon_deg right of the image centre."""
    img = np.full((h, w, 3), 255, np.uint8)
    col = int(round((lon_deg / 360.0 + 0.5) * w)) % w
    img[:, col - 2:col + 3] = 0
    return img


def dark_columns(view):
    g = view.mean(axis=2)
    return [np.flatnonzero(row < 128) for row in g]


def test_a_meridian_is_vertical_and_centred_when_the_view_faces_it():
    v = perspective(equirect_with_meridian(lon_deg=30.0), yaw=30.0, pitch=0.0, fov=60.0, size=(400, 400))
    cols = [c.mean() for c in dark_columns(v)[20:380] if len(c)]
    assert np.mean(cols) == pytest.approx(199.5, abs=1.5)
    assert np.ptp(cols) < 1.5                    # vertical: same column from top to bottom


def test_the_meridian_moves_off_centre_by_the_tangent():
    v = perspective(equirect_with_meridian(lon_deg=30.0), yaw=20.0, pitch=0.0, fov=60.0, size=(400, 400))
    f = 200 / math.tan(math.radians(30))
    expect = 199.5 + f * math.tan(math.radians(10))
    cols = [c.mean() for c in dark_columns(v)[150:250] if len(c)]
    assert np.mean(cols) == pytest.approx(expect, abs=1.5)


def test_pitch_moves_the_horizon():
    h, w = 1024, 2048
    img = np.full((h, w, 3), 255, np.uint8)
    img[h // 2 - 1:h // 2 + 1] = 0                 # the horizon
    v = perspective(img, yaw=0.0, pitch=-10.0, fov=60.0, size=(400, 400))
    rows = np.flatnonzero(v.mean(axis=(1, 2)) < 200)
    f = 200 / math.tan(math.radians(30))
    assert rows.mean() == pytest.approx(199.5 - f * math.tan(math.radians(10)), abs=2.0)


def test_heading_of_a_view_column():
    # The image centre faces the capture azimuth; a column right of centre faces further clockwise.
    assert heading_of_column(azimuth=90.0, yaw=30.0, x=199.5, width=400, fov=60.0) == pytest.approx(120.0)
    assert heading_of_column(azimuth=350.0, yaw=30.0, x=399.5, width=400, fov=60.0) == pytest.approx(50.0)
