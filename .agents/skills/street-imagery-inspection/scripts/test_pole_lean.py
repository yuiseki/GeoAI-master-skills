"""uvx --with numpy --with scikit-image --with pytest pytest test_pole_lean.py"""

# Tests for pole_lean.py on drawn images whose answer is known: a bar at a set angle inside its box, walls of
# vertical edges around it, and the whole picture turned to imitate a camera roll.

import math

import numpy as np
import pytest
from skimage.draw import polygon
from skimage.transform import rotate

from pole_lean import line_angles, pole_lean


def bar(img, x_bottom, y_bottom, length, width, lean_deg, value=0.1):
    """A bar standing at (x_bottom, y_bottom) whose top leans lean_deg to the right."""
    t = math.radians(lean_deg)
    dx, dy = math.sin(t) * length, -math.cos(t) * length
    nx, ny = math.cos(t) * width / 2, math.sin(t) * width / 2
    xs = [x_bottom - nx, x_bottom + nx, x_bottom + dx + nx, x_bottom + dx - nx]
    ys = [y_bottom - ny, y_bottom + ny, y_bottom + dy + ny, y_bottom + dy - ny]
    rr, cc = polygon(ys, xs, img.shape)
    img[rr, cc] = value


def scene(lean, roll=0.0, walls=True):
    img = np.full((600, 600), 0.8)
    if walls:
        for x in (60, 120, 480, 540):                 # building edges: dark stripes, truly vertical
            img[100:550, x:x + 12] = 0.3
    bar(img, 300, 560, 420, 14, lean)
    if roll:
        img = rotate(img, roll, mode="edge")           # counter-clockwise by roll degrees
    return img


BOX = (240, 120, 360, 580)


def test_an_upright_bar_reads_zero():
    r = pole_lean(scene(0.0), BOX)
    assert r["raw_deg"] == pytest.approx(0.0, abs=0.5) and r["lean_deg"] == pytest.approx(0.0, abs=0.5)


@pytest.mark.parametrize("lean", [-6.0, 3.0, 8.0])
def test_a_leaning_bar_reads_its_angle(lean):
    r = pole_lean(scene(lean), BOX)
    assert r["lean_deg"] == pytest.approx(lean, abs=0.6)


def test_a_rolled_camera_is_corrected_by_the_walls():
    r = pole_lean(scene(5.0, roll=2.0), BOX)
    # rotate() turns the picture counter-clockwise, so every vertical line now leans 2 degrees to the left.
    assert r["reference_deg"] == pytest.approx(-2.0, abs=0.5)
    assert r["raw_deg"] == pytest.approx(3.0, abs=0.7)
    assert r["lean_deg"] == pytest.approx(5.0, abs=0.7)


def test_without_walls_there_is_no_correction_and_it_says_so():
    r = pole_lean(scene(4.0, walls=False), BOX)
    assert r["reference_lines"] == 0 and r["corrected"] is False
    assert r["lean_deg"] == pytest.approx(4.0, abs=0.6)


def test_no_pole_in_the_box_gives_no_angle():
    img = np.full((600, 600), 0.8)
    r = pole_lean(img, BOX)
    assert r["pole_lines"] == 0 and r["lean_deg"] is None


def test_line_angles_sign():
    img = np.full((300, 300), 0.8)
    bar(img, 150, 280, 220, 10, 10.0)
    ang, lens = line_angles(img, min_length=60, max_tilt=20)
    assert np.average(ang, weights=lens) == pytest.approx(10.0, abs=0.8)
