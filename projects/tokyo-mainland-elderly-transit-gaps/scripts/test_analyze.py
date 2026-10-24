"""Small known-answer checks for the task-39 network and ranking."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("transit_gaps", Path(__file__).with_name("analyze.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_mesh_bounds_tokyo_station():
    assert MODULE.mesh_bounds("53394611") == pytest.approx((139.7625, 35.675, 139.775, 35.6833333333))


def test_census_secrecy_is_not_zero_and_prefecture_parts_not_mixed():
    rows = [
        ("53394611", "13", "100", "20", "8", "0"),
        ("53394611", "14", "50", "40", "30", "0"),
        ("53394612", "13", "12", "*", "*", "2"),
    ]
    result = MODULE.aggregate_census(rows)
    assert result["53394611"]["age65"] == 20
    assert result["53394611"]["total"] == 100
    assert result["53394612"]["age65"] is None


def test_census_partial_missing_age_is_unknown_not_a_type_error():
    rows = [("53394613", "13", "100", "20", "*", "0")]
    assert MODULE.aggregate_census(rows)["53394613"]["age75"] is None


def test_graph_uses_road_detour_not_straight_line_and_disconnected_is_unknown():
    lines = [[(0.0, 0.0), (0.0, 100.0), (100.0, 100.0), (100.0, 0.0)],
             [(1000.0, 0.0), (1100.0, 0.0)]]
    graph, coords, _ = MODULE.build_graph(lines)
    bus = MODULE.multi_source_distances(graph, coords, [(100.0, 0.0)], max_snap_m=1)
    assert MODULE.distance_from_point((0.0, 0.0), coords, bus, max_snap_m=1) == pytest.approx(300)
    assert MODULE.distance_from_point((1000.0, 0.0), coords, bus, max_snap_m=1) is None


def test_classification_requires_both_distances_and_prefers_number_not_share():
    rows = [
        {"mesh": "a", "age65": 200, "age75": 70, "total": 1000, "bus_m": 900, "rail_m": 1600},
        {"mesh": "b", "age65": 40, "age75": 25, "total": 50, "bus_m": 1100, "rail_m": 1800},
        {"mesh": "c", "age65": 300, "age75": 120, "total": 1000, "bus_m": 700, "rail_m": 5000},
    ]
    assert [r["mesh"] for r in MODULE.rank_gaps(rows, bus_threshold=800, rail_threshold=1500)] == ["a", "b"]


def test_walkable_filter_rejects_motorways_steps_and_private():
    assert MODULE.walkable("footway", None, None)
    assert MODULE.walkable("residential", None, None)
    assert not MODULE.walkable("steps", None, None)
    assert not MODULE.walkable("motorway", None, None)
    assert not MODULE.walkable("path", "no", None)
    assert not MODULE.walkable("path", None, "private")


def test_multipoint_fraction_requires_every_sample_to_be_reachable():
    assert MODULE.sample_gap_fraction([(900, 1600), (700, 1800)], 800, 1500) == pytest.approx(0.5)
    assert MODULE.sample_gap_fraction([(900, 1600), (None, 1800)], 800, 1500) is None
