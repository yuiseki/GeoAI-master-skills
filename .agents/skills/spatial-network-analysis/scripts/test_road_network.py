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


def _grid_network(n=5, step_m=100.0, lat0=35.0, lon0=139.0):
    """An n x n street grid, step_m apart, one segment per block side."""
    dlat = step_m / (math.pi * 6371000.0 / 180)
    dlon = dlat / math.cos(math.radians(lat0))
    pt = lambda r, c: (lon0 + c * dlon, lat0 + r * dlat)
    segs = []
    for r in range(n):
        for c in range(n):
            for dr, dc in ((0, 1), (1, 0)):
                if r + dr < n and c + dc < n:
                    a, b = f"{r}-{c}", f"{r + dr}-{c + dc}"
                    segs.append({"id": f"{a}_{b}", "class": "residential",
                                 "geometry": LineString([pt(r, c), pt(r + dr, c + dc)]),
                                 "connectors": [{"connector_id": a, "at": 0.0}, {"connector_id": b, "at": 1.0}]})
    edges, nodes = build_edges(segs)
    return Network(edges, nodes), pt(n // 2, n // 2)


def test_service_area_counts_the_reached_street_length_including_partial_edges():
    from road_network import service_area

    net, (lon, lat) = _grid_network()
    sa = service_area(net, lon, lat, 150.0, buffer_m=1.0)
    # 4 full blocks from the centre (400 m) and from each of the 4 neighbours, 50 m along each of its other
    # 3 sides (600 m): 1,000 m of street.
    assert sa["reached_length_m"] == pytest.approx(1000, rel=0.01)
    assert sa["area_edges_m2"] == pytest.approx(2 * 1000, rel=0.1)  # a 1 m buffer on each side
    assert sa["area_hull_m2"] > 10 * sa["area_edges_m2"]  # the hull covers the blocks between the streets


def test_service_area_grows_with_the_distance_and_the_hull_overstates_it():
    from road_network import service_area

    net, (lon, lat) = _grid_network(9)
    small = service_area(net, lon, lat, 150.0, buffer_m=25.0)
    large = service_area(net, lon, lat, 350.0, buffer_m=25.0)
    assert large["area_edges_m2"] > small["area_edges_m2"]
    assert large["area_hull_m2"] >= large["area_edges_m2"] * 0.9
    # A long edge that is reached from both ends but not in the middle is not filled in.
    assert large["reached_length_m"] < net.total_length_m


def test_a_long_edge_reached_from_both_ends_keeps_its_unreached_middle_out():
    from road_network import service_area

    # O to B (100 m east) and O to C (100 m north), and a 300 m road from B to C that bends far out.
    dlat = 100 / (math.pi * 6371000.0 / 180)
    dlon = dlat / math.cos(math.radians(35))
    O, B, C = (139.0, 35.0), (139.0 + dlon, 35.0), (139.0, 35.0 + dlat)
    bend = (139.0 + dlon * 1.6, 35.0 + dlat * 1.6)
    segs = [{"id": "ob", "class": "r", "geometry": LineString([O, B]),
             "connectors": [{"connector_id": "O", "at": 0.0}, {"connector_id": "B", "at": 1.0}]},
            {"id": "oc", "class": "r", "geometry": LineString([O, C]),
             "connectors": [{"connector_id": "O", "at": 0.0}, {"connector_id": "C", "at": 1.0}]},
            {"id": "bc", "class": "r", "geometry": LineString([B, bend, C]),
             "connectors": [{"connector_id": "B", "at": 0.0}, {"connector_id": "C", "at": 1.0}]}]
    edges, nodes = build_edges(segs)
    sa = service_area(Network(edges, nodes), *O, 150.0, buffer_m=1.0)
    # 100 + 100 to B and C, then 50 m into the long road from each end; its middle stays out.
    assert sa["reached_length_m"] == pytest.approx(300, rel=0.01)
