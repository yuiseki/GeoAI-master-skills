"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with numpy --with pandas --with shapely --with scipy --with pytest pytest -q -p no:cacheprovider test_build_network.py"""

import math

import numpy as np
import pytest

from build_network import build_graph, multi_source_distances, self_test, snap_points, walkable


def test_walkable_classes_and_access():
    assert walkable("residential", None, None)
    assert not walkable("motorway", None, None)
    assert not walkable("steps", None, None) and walkable("steps", None, None, include_steps=True)
    assert not walkable("footway", "no", None) and not walkable("footway", None, "private")
    assert walkable("footway", "yes", "no") is False


def test_build_graph_merges_shared_vertices_and_keeps_the_shorter_duplicate():
    lines = [
        [(0, 0), (3, 4), (3, 10)],          # 5 m + 6 m
        [(3.001, 4.001), (3, 10)],          # same nodes as the second segment once rounded to 1 cm; 6 m again
        [(0, 0)],                           # too short: counted as a line, adds nothing
        [(3, 10), (3, 10)],                 # zero length: skipped
    ]
    graph, positions, info = build_graph(lines)
    assert info["lines"] == 4 and info["nodes"] == 3 and info["edges"] == 2
    assert info["length_km"] == pytest.approx(11 / 1000, rel=1e-3)
    assert graph[0, 1] == pytest.approx(5.0) and graph[1, 0] == pytest.approx(5.0)
    with pytest.raises(ValueError):
        build_graph([[(0, 0)]])


def test_snap_points_marks_points_beyond_the_limit():
    coords = np.array([[0.0, 0.0], [100.0, 0.0]])
    assert snap_points([(90.0, 0.0), (300.0, 0.0)], coords, max_snap_m=50) == [(1, 10.0), (None, 200.0)]
    assert snap_points([], coords, max_snap_m=50) == []


def test_multi_source_takes_the_nearest_of_several_destinations():
    graph, coords, _ = build_graph([[(0, 0), (100, 0), (200, 0), (300, 0)]])
    # destinations 10 m from node 0 and 0 m from node 3: node 1 is 110 from the first, 200 from the second
    d, snapped = multi_source_distances(graph, coords, [(0.0, 10.0), (300.0, 0.0)], max_snap_m=50)
    assert d.tolist() == pytest.approx([10.0, 110.0, 100.0, 0.0], abs=1e-4)
    d, _ = multi_source_distances(graph, coords, [(0.0, 900.0)], max_snap_m=50)
    assert all(math.isinf(x) for x in d)


def test_the_scripts_own_self_test_passes():
    self_test()
