"""uvx --with numpy --with scipy --with scikit-learn --with shapely --with duckdb --with pytest pytest test_road_network.py"""

import math

import numpy as np
import pytest
from shapely.geometry import LineString

from road_network import Network, build_edges, line_length_m


def haversine_m(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def seg(id_, coords, connectors, cls="residential"):
    return {"id": id_, "class": cls, "geometry": LineString(coords),
            "connectors": [{"connector_id": c, "at": at} for c, at in connectors]}


def test_length_is_great_circle_at_high_latitude():
    line = LineString([(0, 60), (0.5, 60), (1, 60)])
    expected = haversine_m(0, 60, 0.5, 60) + haversine_m(0.5, 60, 1, 60)
    assert line_length_m(line) == pytest.approx(expected, rel=1e-9)


def test_a_segment_is_split_at_its_connectors():
    s = seg("s", [(0, 60), (1, 60)], [("a", 0.0), ("m", 0.5), ("b", 1.0)])
    edges, nodes = build_edges([s])
    assert sorted((e["u"], e["v"]) for e in edges) == [("a", "m"), ("m", "b")]
    total = haversine_m(0, 60, 1, 60)
    assert sum(e["length_m"] for e in edges) == pytest.approx(total, rel=1e-6)
    # The middle connector sits halfway along the line, by length.
    lon, lat = nodes["m"]
    assert haversine_m(0, 60, lon, lat) == pytest.approx(total / 2, rel=1e-3)


def test_connectors_need_not_be_listed_in_order():
    s = seg("s", [(0, 0), (0.02, 0)], [("b", 1.0), ("a", 0.0), ("m", 0.25)])
    edges, _ = build_edges([s])
    lengths = {(e["u"], e["v"]): e["length_m"] for e in edges}
    assert lengths[("m", "b")] == pytest.approx(3 * lengths[("a", "m")], rel=1e-6)


def test_shortest_path_runs_through_shared_connectors():
    segs = [seg("s1", [(0, 0), (0.01, 0)], [("a", 0), ("b", 1)]),
            seg("s2", [(0.01, 0), (0.01, 0.01)], [("b", 0), ("c", 1)]),
            seg("s3", [(0, 0), (0.01, 0.01)], [("a", 0), ("c", 1)], cls="footway")]
    walk = Network(*build_edges(segs))
    drive = Network(*build_edges([s for s in segs if s["class"] != "footway"]))
    d_walk = walk.distances(["a"], ["c"])[0, 0]
    d_drive = drive.distances(["a"], ["c"])[0, 0]
    assert d_walk == pytest.approx(haversine_m(0, 0, 0.01, 0.01), rel=1e-6)
    assert d_drive == pytest.approx(haversine_m(0, 0, 0.01, 0) + haversine_m(0.01, 0, 0.01, 0.01),
                                    rel=1e-6)


def test_unreachable_pairs_are_infinite_not_zero():
    segs = [seg("s1", [(0, 0), (0.01, 0)], [("a", 0), ("b", 1)]),
            seg("s2", [(1, 1), (1.01, 1)], [("c", 0), ("d", 1)])]
    net = Network(*build_edges(segs))
    d = net.distances(["a"], ["b", "c"])
    assert d[0, 0] > 0 and np.isinf(d[0, 1])
    assert net.components()["count"] == 2


def test_points_snap_to_the_nearest_node_by_great_circle():
    # At 60N a node 0.9 degree of longitude away (~50 km) is nearer than one 0.6 degree of
    # latitude away (~67 km).
    segs = [seg("s1", [(0.9, 60), (0.9, 60.1)], [("east", 0), ("e2", 1)]),
            seg("s2", [(0, 60.6), (0, 60.7)], [("north", 0), ("n2", 1)])]
    net = Network(*build_edges(segs))
    node, dist_m = net.snap(np.array([0.0]), np.array([60.0]))
    assert node[0] == "east"
    assert dist_m[0] == pytest.approx(haversine_m(0, 60, 0.9, 60), rel=1e-6)


def test_parallel_segments_keep_the_shorter():
    segs = [seg("short", [(0, 0), (0.01, 0)], [("a", 0), ("b", 1)]),
            seg("long", [(0, 0), (0.005, 0.005), (0.01, 0)], [("a", 0), ("b", 1)])]
    net = Network(*build_edges(segs))
    assert net.distances(["a"], ["b"])[0, 0] == pytest.approx(haversine_m(0, 0, 0.01, 0), rel=1e-6)


def test_a_connector_on_a_later_leg_of_a_bent_line_is_placed_on_that_leg():
    # An L-shaped line with two legs of equal length; at = 0.75 is halfway along the second leg.
    s = seg("s", [(0, 0), (0.01, 0), (0.01, 0.01)], [("a", 0.0), ("q", 0.75), ("b", 1.0)])
    _, nodes = build_edges([s])
    lon, lat = nodes["q"]
    assert lon == pytest.approx(0.01, abs=1e-6)
    assert lat == pytest.approx(0.005, abs=1e-5)


def test_snapping_can_skip_small_islands_of_the_network():
    # A two-node island (an unconnected station passage) lies nearer the point than the main grid.
    main = [seg(f"m{i}", [(0.001 * i, 0.002), (0.001 * (i + 1), 0.002)], [(f"n{i}", 0), (f"n{i+1}", 1)])
            for i in range(5)]
    island = [seg("island", [(0.0, 0.0), (0.0001, 0.0)], [("i0", 0), ("i1", 1)])]
    net = Network(*build_edges(main + island))
    anywhere, _ = net.snap(np.array([0.00002]), np.array([0.0]))
    largest, dist_m = net.snap(np.array([0.00002]), np.array([0.0]), largest_only=True)
    assert anywhere[0] in ("i0", "i1")
    assert largest[0].startswith("n")
    assert dist_m[0] > 100


def test_distance_matrix_adds_snapping_and_keeps_straight_line_for_comparison():
    from road_network import distance_matrix

    segs = [seg("s1", [(0, 0), (0.01, 0)], [("a", 0), ("b", 1)]),
            seg("s2", [(0.01, 0), (0.01, 0.01)], [("b", 0), ("c", 1)])]
    net = Network(*build_edges(segs))
    # Origins next to a and c, one destination next to c.
    m = distance_matrix(net, np.array([0.0, 0.01]), np.array([0.0001, 0.0101]),
                        np.array([0.01]), np.array([0.0099]))
    assert m["network_m"].shape == (2, 1)
    along = haversine_m(0, 0, 0.01, 0) + haversine_m(0.01, 0, 0.01, 0.01)
    assert m["network_m"][0, 0] == pytest.approx(along, rel=1e-6)
    assert m["network_m"][1, 0] == pytest.approx(0.0, abs=1e-3)
    assert m["origin_snap_m"][0] == pytest.approx(haversine_m(0, 0.0001, 0, 0), rel=1e-6)
    assert m["straight_m"][0, 0] == pytest.approx(haversine_m(0.0, 0.0001, 0.01, 0.0099), rel=1e-6)
