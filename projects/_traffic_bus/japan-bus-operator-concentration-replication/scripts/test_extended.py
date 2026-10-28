"""uv run --no-project --with pytest --with numpy --with scipy python3 -m pytest -q projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/test_extended.py"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from analysis import mesh_center, unit_xyz
from extended import classify_single_kind, inspect_mesh, mesh_bounds


def test_mesh_bounds_include_centre_and_exclude_next_east_cell():
    code = "53394611"
    west, south, east, north = mesh_bounds(code)
    lon, lat = mesh_center(code)
    assert west < lon < east and south < lat < north
    assert east - west == pytest.approx(1 / 80)
    assert north - south == pytest.approx(1 / 120)


def test_inspect_mesh_distinguishes_grid_cell_from_800m_and_deduplicates_routes():
    code = "53394611"
    lon, lat = mesh_center(code)
    stop_rows = [
        (lon + 0.001, lat, "A", (1,), ("R1",)),
        (lon + 0.002, lat, "A", (1,), ("R1",)),
        (lon + 0.007, lat, "B", (3,), ("R2",)),
    ]
    result = inspect_mesh(code, lon, lat, (0, 1, 2), stop_rows, radius_m=800)
    assert result["operators_800m"] == 2
    assert result["operators_in_mesh"] == 1
    assert result["single_kind"] is None
    assert result["route_pairs"] is None


def test_single_kind_requires_every_route_same_kind():
    assert classify_single_kind(((1, 1), (1,))) == "private"
    assert classify_single_kind(((3,), (3,))) == "community"
    assert classify_single_kind(((2,),)) == "public"
    assert classify_single_kind(((1,), (3,))) == "mixed"
    assert classify_single_kind(((5,),)) == "mixed"
    with pytest.raises(ValueError):
        classify_single_kind(())


def test_single_operator_can_have_multiple_distinct_route_names():
    code = "53394611"
    lon, lat = mesh_center(code)
    stops = [
        (lon, lat, "A", (1, 1), ("R1", "R2")),
        (lon + 0.001, lat, "A", (1,), ("R1",)),
    ]
    result = inspect_mesh(code, lon, lat, (0, 1), stops, radius_m=800)
    assert result["operators_800m"] == 1
    assert result["single_kind"] == "private"
    assert result["route_pairs"] == 2


def test_cached_xyz_and_direct_path_agree():
    code = "53394611"
    lon, lat = mesh_center(code)
    stops = [(lon + 0.001, lat, "A", (1,), ("R",))]
    point_xyz = unit_xyz(np.array([lon]), np.array([lat]))[0]
    stops_xyz = unit_xyz(np.array([stops[0][0]]), np.array([stops[0][1]]))
    assert inspect_mesh(code, lon, lat, (0,), stops, 800) == inspect_mesh(
        code, lon, lat, (0,), stops, 800, point_xyz=point_xyz, stops_xyz=stops_xyz
    )
