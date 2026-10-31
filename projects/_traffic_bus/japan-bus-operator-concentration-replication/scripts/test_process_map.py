"""uv run --no-project --with pytest --with numpy --with scipy python3 -m pytest -q projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/test_process_map.py"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from analysis import EARTH_KM, mesh_center
from process_map import circle_lonlat, mesh_class, mesh_square, pick_examples, stops_within


def test_mesh_square_holds_the_center_and_is_one_third_mesh():
    xmin, ymin, xmax, ymax = mesh_square("64432584")
    lon, lat = mesh_center("64432584")
    assert xmin < lon < xmax and ymin < lat < ymax
    assert xmax - xmin == pytest.approx(1 / 80)
    assert ymax - ymin == pytest.approx(1 / 120)
    assert (xmin + xmax) / 2 == pytest.approx(lon)


def test_mesh_class_keeps_unknown_age_out_of_the_denominator():
    assert mesh_class(0, 120) == "0"
    assert mesh_class(1, 120) == "1"
    assert mesh_class(3, 120) == "2+"
    assert mesh_class(2, None) == "out"
    assert mesh_class(2, 0) == "out"


def test_pick_examples_takes_the_largest_older_population_per_class():
    rows = [
        {"mesh_code": "a", "age65": 50, "operators_800m": 2},
        {"mesh_code": "b", "age65": 90, "operators_800m": 3},
        {"mesh_code": "c", "age65": 70, "operators_800m": 1},
        {"mesh_code": "d", "age65": None, "operators_800m": 1},
        {"mesh_code": "e", "age65": 10, "operators_800m": 0},
    ]
    picked = pick_examples(rows)
    assert [r["mesh_code"] for r in picked] == ["b", "c", "e"]


def test_pick_examples_stops_when_a_class_is_missing():
    with pytest.raises(ValueError):
        pick_examples([{"mesh_code": "a", "age65": 5, "operators_800m": 1}])


def test_stops_within_uses_the_great_circle_radius():
    lon, lat = 143.2, 42.9
    step = math.degrees(0.79 / EARTH_KM)
    stops = [("A", lon, lat + step), ("B", lon, lat + step * 1.03), ("A", lon, lat)]
    inside = stops_within(lon, lat, stops, 800)
    assert [s[0] for s in inside] == ["A", "A"]


def test_circle_lonlat_points_are_on_the_radius():
    lon, lat = 143.2, 42.9
    for x, y in circle_lonlat(lon, lat, 800, n=12):
        a = math.radians(lat)
        b = math.radians(y)
        d = 2 * math.asin(math.sqrt(math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(x - lon) / 2) ** 2))
        assert d * EARTH_KM * 1000 == pytest.approx(800, rel=1e-3)
