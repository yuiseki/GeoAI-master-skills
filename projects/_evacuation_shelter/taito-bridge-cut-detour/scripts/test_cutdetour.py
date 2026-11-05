"""uvx --with numpy --with scipy --with shapely --with pytest pytest scripts/test_cutdetour.py"""
import numpy as np
from shapely.geometry import LineString

from cutdetour import build_graph, cluster_lines, cut_distances, snap, worst_cut, multi_source


def river_world(bridges_x, parallel=False):
    """Two banks (y=0 and y=100) joined by vertical bridges at the given x. Shelter on the north bank at x=0.

    Each bank is a road from x=-1000 to x=1000 with vertices every 100 m. With parallel=True every bridge is drawn
    as 3 lines 4 m apart (carriageway and two sidewalks), joined to the banks by short links.
    """
    lines, is_bridge = [], []
    xs = np.arange(-1000, 1001, 100)
    for y in (0, 100):
        lines.append(LineString([(x, y) for x in xs]))
        is_bridge.append(False)
    for bx in bridges_x:
        offs = (-4, 0, 4) if parallel else (0,)
        for o in offs:
            lines.append(LineString([(bx + o, 0), (bx + o, 50), (bx + o, 100)]) if o == 0 else
                         LineString([(bx + o, 10), (bx + o, 90)]))
            is_bridge.append(True)
            if o != 0:  # sidewalks reach the carriageway by short links on both banks
                lines.append(LineString([(bx, 0), (bx + o, 10)]))
                is_bridge.append(False)
                lines.append(LineString([(bx + o, 90), (bx, 100)]))
                is_bridge.append(False)
    return lines, np.array(is_bridge)


def test_single_bridge_cut_is_unreachable():
    lines, isb = river_world([0])
    g = build_graph(lines)
    src, _ = snap(g, [(0, 100)])
    org, _ = snap(g, [(500, 0)])
    groups = cluster_lines(lines, np.flatnonzero(isb), 10)
    d0, cuts = cut_distances(g, src, groups, org)
    assert np.isclose(d0[0], 600)
    dstar, who = worst_cut(d0, cuts)
    assert np.isinf(dstar[0]) and who[0] == groups[int(np.flatnonzero(isb)[0])]


def test_two_bridges_detour():
    lines, isb = river_world([0, 800])
    g = build_graph(lines)
    src, _ = snap(g, [(0, 100)])
    org, _ = snap(g, [(500, 0)])
    groups = cluster_lines(lines, np.flatnonzero(isb), 10)
    d0, cuts = cut_distances(g, src, groups, org)
    dstar, _ = worst_cut(d0, cuts)
    # via x=800: 300 along south bank + 100 across + 800 back west
    assert np.isclose(d0[0], 600) and np.isclose(dstar[0], 1200)


def test_unused_bridge_is_not_cut():
    lines, isb = river_world([0, 800])
    g = build_graph(lines)
    src, _ = snap(g, [(0, 100)])
    org, _ = snap(g, [(-500, 0)])
    groups = cluster_lines(lines, np.flatnonzero(isb), 10)
    d0, cuts = cut_distances(g, src, groups, org)
    assert len(cuts) == 1  # only the bridge at x=0 lies on the path


def test_parallel_lines_must_be_grouped():
    lines, isb = river_world([0, 800], parallel=True)
    g = build_graph(lines)
    src, _ = snap(g, [(0, 100)])
    org, _ = snap(g, [(500, 0)])
    single = {int(i): k for k, i in enumerate(np.flatnonzero(isb))}  # every line its own structure
    d0, cuts = cut_distances(g, src, single, org)
    dstar, _ = worst_cut(d0, cuts)
    assert np.isclose(dstar[0], d0[0], atol=20)  # a sidewalk still crosses: no real detour
    grouped = cluster_lines(lines, np.flatnonzero(isb), 10)
    assert len(set(grouped.values())) == 2
    d0, cuts = cut_distances(g, src, grouped, org)
    dstar, _ = worst_cut(d0, cuts)
    assert dstar[0] > d0[0] + 500


def test_parallel_edges_keep_shortest_not_sum():
    lines = [LineString([(0, 0), (100, 0)]), LineString([(0, 0), (50, 50), (100, 0)])]
    g = build_graph(lines)
    d = multi_source(g, snap(g, [(0, 0)])[0])
    assert np.isclose(d[snap(g, [(100, 0)])[0][0]], 100)


def test_lines_join_only_at_shared_vertices():
    # a bridge crossing over a road without a shared vertex does not connect to it
    lines = [LineString([(-100, 0), (100, 0)]), LineString([(0, -100), (0, 100)])]
    g = build_graph(lines)
    assert len(set(g.comp)) == 2


def test_half_mesh_tokyo_station():
    import importlib
    run = importlib.import_module("02_run")
    code = run.half_mesh(139.7671, 35.6812)
    assert code[:8] == "53394611"  # the census card's example
    # SW corner of 53394611 is lat 35.6750, lon 139.7625. The station is 0.0062 deg north (> 1/240, north half)
    # and 0.0046 deg east (< 1/160, west half): quadrant 3 (NW)
    assert code[8] == "3"


def test_origin_on_bridge_deck_is_snapped_to_ground():
    from cutdetour import ground_nodes
    lines, isb = river_world([0, 800])
    g = build_graph(lines)
    ground = ground_nodes(g, np.flatnonzero(isb))
    src, _ = snap(g, [(0, 100)], allowed=ground)
    # a point in the river next to the x=800 bridge
    on_deck, _ = snap(g, [(801, 50)])
    off_deck, dist = snap(g, [(801, 50)], allowed=ground)
    groups = cluster_lines(lines, np.flatnonzero(isb), 10)
    dstar, _ = worst_cut(*cut_distances(g, src, groups, on_deck))
    assert np.isinf(dstar[0])  # the artefact: the deck node is cut off with its bridge
    dstar, _ = worst_cut(*cut_distances(g, src, groups, off_deck))
    assert np.isfinite(dstar[0]) and dist[0] > 40


def test_small_ground_pocket_is_not_a_snap_target():
    from cutdetour import ground_nodes
    lines, isb = river_world([0, 800])
    # a 30 m pocket on the far side of a third bridge at x=400 (like stairs reached only from a deck)
    lines = lines + [LineString([(400, 100), (400, 130)]), LineString([(400, 130), (430, 130)])]
    isb = np.r_[isb, True, False]
    g = build_graph(lines)
    near_pocket = [(431, 131)]
    n_any, _ = snap(g, near_pocket, allowed=ground_nodes(g, np.flatnonzero(isb)))
    n_big, _ = snap(g, near_pocket, allowed=ground_nodes(g, np.flatnonzero(isb), min_component_m=1000))
    assert np.allclose(g.xy[n_any[0]], (430, 130))
    assert g.xy[n_big[0]][1] == 100  # snapped to the north bank road instead
