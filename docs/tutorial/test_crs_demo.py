"""uvx --python 3.12 --with numpy --with pytest pytest -q test_crs_demo.py"""

# Tests for crs_demo.py: the length of a degree, and what swapping lon and lat does to a distance.
# The README of docs/tutorial prints the script's output; that table is the promise checked here.

import math
import runpy
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).parent
SCRIPT = HERE / "crs_demo.py"


@pytest.fixture(scope="module")
def demo():
    """Run the script once in-process and keep its globals (haversine_km, right, swapped)."""
    return runpy.run_path(str(SCRIPT), run_name="crs_demo")


def test_one_degree_along_the_equator_is_a_360th_of_the_circumference(demo):
    # 2 * pi * 6371 / 360 = 111.195 km, the same along a meridian anywhere
    assert demo["haversine_km"](0, 0, 1, 0) == pytest.approx(2 * math.pi * 6371 / 360)
    assert demo["haversine_km"](0, 60, 0, 61) == pytest.approx(2 * math.pi * 6371 / 360)


def test_a_degree_of_longitude_shrinks_with_the_cosine_of_latitude(demo):
    # along a parallel the great circle is a little shorter than R cos(lat) dlon, so compare to 0.1 km
    for lat in (35, 60, 80):
        assert demo["haversine_km"](0, lat, 1, lat) == pytest.approx(
            2 * math.pi * 6371 / 360 * math.cos(math.radians(lat)), abs=0.1)


def test_distance_is_symmetric_zero_for_one_point_and_half_the_circumference_for_antipodes(demo):
    h = demo["haversine_km"]
    assert h(10.75, 59.91, 24.94, 60.17) == pytest.approx(h(24.94, 60.17, 10.75, 59.91))
    assert h(139.7, 35.7, 139.7, 35.7) == 0
    assert h(0, 0, 180, 0) == pytest.approx(math.pi * 6371)


def test_haversine_works_on_arrays(demo):
    d = demo["haversine_km"](np.zeros(3), np.zeros(3), np.array([0, 1, 2]), np.zeros(3))
    assert d == pytest.approx([0, 111.195, 222.390], abs=1e-3)


def test_swapping_lon_and_lat_doubles_oslo_to_helsinki(demo):
    # the comment in the script says about 790 km; with lat and lon swapped the 14 degree lat gap dominates
    assert round(demo["right"]) == 787
    assert round(demo["swapped"]) == 1578


def test_the_printed_output_is_the_table_in_the_readme():
    out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True).stdout
    expected = """緯度ごとの、経度 1 度の長さと、1 度 x 1 度の格子の面積
緯度    経度1度(km)   緯度1度(km)   格子の面積(km2)
  0度       111.2         111.2           12364
 35度        91.1         111.2           10128
 60度        55.6         111.2            6182
 80度        19.3         111.2            2147

オスロからヘルシンキ (経度, 緯度の順に渡す): 787 km
オスロからヘルシンキ (緯度, 経度を取り違えた): 1578 km
"""
    assert out == expected
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    for line in expected.splitlines()[1:]:
        assert line in readme
