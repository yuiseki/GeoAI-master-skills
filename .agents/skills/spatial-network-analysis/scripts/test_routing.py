"""uvx --with numpy --with pytest pytest test_routing.py

Small hand-drawn graphs; every expected cost is added up by hand. Coordinates are metres.
"""

import math

import pytest

from routing import arcs_for, parse_speed, route, snap, travel_times


def edge(i, u, v, length, cls="residential", oneway=None, maxspeed=None):
    return {"id": i, "u": u, "v": v, "length_m": length, "class": cls, "oneway": oneway, "maxspeed": maxspeed}


def test_a_one_way_street_is_one_arc_and_a_two_way_street_is_two():
    arcs = arcs_for([edge("ab", "A", "B", 100, oneway="yes"), edge("bc", "B", "C", 100),
                     edge("cd", "C", "D", 100, oneway="-1")], "drive")
    assert sorted((a["tail"], a["head"]) for a in arcs) == [("A", "B"), ("B", "C"), ("C", "B"), ("D", "C")]


def test_ignoring_one_way_streets_finds_a_route_a_car_cannot_drive():
    edges = [edge("ab", "A", "B", 100, oneway="yes"), edge("bc", "B", "C", 100)]
    assert route(arcs_for(edges, "drive"), "C", "A")["cost"] == math.inf
    assert route(arcs_for(edges, "drive", respect_oneway=False), "C", "A")["cost"] == 200  # not drivable
    assert route(arcs_for(edges, "walk"), "C", "A")["cost"] == 200  # a pedestrian may walk against it


def test_a_turn_restriction_forbids_the_shortcut():
    # A -> B -> C is a left turn at B that is banned; the way round is B -> E -> F -> C
    edges = [edge("ab", "A", "B", 100), edge("bc", "B", "C", 100), edge("be", "B", "E", 100),
             edge("ef", "E", "F", 100), edge("fc", "F", "C", 100)]
    arcs = arcs_for(edges, "drive")
    assert route(arcs, "A", "C")["cost"] == 200
    r = route(arcs, "A", "C", restrictions=[("ab", "B", "bc")])
    assert r["cost"] == 400
    assert r["nodes"] == ["A", "B", "E", "F", "C"]


def test_u_turns_are_refused_unless_allowed():
    # Without the loop, the only way to obey the ban is to go on to E and turn back
    edges = [edge("ab", "A", "B", 100), edge("bc", "B", "C", 100), edge("be", "B", "E", 100)]
    arcs = arcs_for(edges, "drive")
    assert route(arcs, "A", "C", restrictions=[("ab", "B", "bc")])["cost"] == math.inf
    r = route(arcs, "A", "C", restrictions=[("ab", "B", "bc")], u_turns=True)
    assert r["cost"] == 400 and r["nodes"] == ["A", "B", "E", "B", "C"]


def test_the_shortest_route_and_the_fastest_route_differ():
    # direct residential 1,000 m at 20 km/h (180 s); round by the primary road 1,500 m at 60 km/h (90 s)
    edges = [edge("ab", "A", "B", 1000, maxspeed="20"), edge("ac", "A", "C", 700, "primary", maxspeed="60"),
             edge("cb", "C", "B", 800, "primary", maxspeed="60")]
    arcs = arcs_for(edges, "drive")
    travel_times(arcs)
    short = route(arcs, "A", "B", weight="length_m")
    fast = route(arcs, "A", "B", weight="time_s")
    assert short["nodes"] == ["A", "B"] and short["cost"] == 1000
    assert fast["nodes"] == ["A", "C", "B"] and fast["cost"] == pytest.approx(90)


def test_speed_units_are_read_and_unknown_text_is_not_a_speed():
    assert parse_speed("50") == 50
    assert parse_speed("50 km/h") == 50
    assert parse_speed("30 mph") == pytest.approx(48.28032)
    for text in (None, "", "none", "signals", "walk"):
        assert parse_speed(text) is None


def test_a_missing_speed_is_assumed_only_when_told_and_is_counted():
    arcs = arcs_for([edge("ab", "A", "B", 1000, maxspeed="40"), edge("bc", "B", "C", 600, "tertiary")], "drive")
    with pytest.raises(ValueError, match="no speed"):
        travel_times(arcs)
    n = travel_times(arcs, assumed_kmh={"tertiary": 36})
    assert n == {"tagged": 2, "assumed": 2}
    bc = next(a for a in arcs if a["tail"] == "B" and a["head"] == "C")
    assert bc["time_s"] == pytest.approx(600 / 10) and bc["speed_source"] == "assumed"


def test_walking_and_driving_use_different_graphs():
    edges = [edge("ab", "A", "B", 300, "footway"), edge("ac", "A", "C", 300), edge("cb", "C", "B", 300),
             edge("ad", "A", "D", 100, "motorway")]
    assert route(arcs_for(edges, "walk"), "A", "B")["cost"] == 300
    assert route(arcs_for(edges, "drive"), "A", "B")["cost"] == 600
    assert route(arcs_for(edges, "walk"), "A", "D")["cost"] == math.inf  # no walking on a motorway


def test_a_disconnected_destination_is_unreachable_not_zero():
    arcs = arcs_for([edge("ab", "A", "B", 100), edge("cd", "C", "D", 100)], "drive")
    r = route(arcs, "A", "D")
    assert r["cost"] == math.inf and r["nodes"] == []
    assert route(arcs, "A", "A")["cost"] == 0


def test_snapping_reports_the_distance_and_flags_points_too_far_from_the_network():
    nodes = {"A": (0, 0), "B": (100, 0)}
    s = snap([(10, 5), (90, 300)], nodes, max_m=50)
    assert [x["node"] for x in s] == ["A", "B"]
    assert s[0]["distance_m"] == pytest.approx(math.hypot(10, 5)) and s[0]["ok"]
    assert s[1]["distance_m"] == pytest.approx(math.hypot(10, 300)) and not s[1]["ok"]
