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


def pocket_world():
    """A 200 m street with a shelter at its west end, a parallel street 100 m north joined at both ends,
    and a 300 m dead-end street (a pocket) leaving the main street at x=150 southwards."""
    lines = [LineString([(x, 0) for x in range(0, 201, 25)]),            # main street
             LineString([(0, 0), (0, 100)]), LineString([(200, 0), (200, 100)]),
             LineString([(0, 100), (200, 100)]),                         # parallel street
             LineString([(150, 0), (150, -150), (150, -300)])]           # pocket street
    # short stubs make the four corners junctions (without them the block's outline is one loop section)
    lines += [LineString([(0, 0), (-20, 0)]), LineString([(200, 0), (220, 0)]),
              LineString([(0, 100), (-20, 100)]), LineString([(200, 100), (220, 100)])]
    return lines


def test_sections_split_at_junctions():
    from cutdetour import sections
    g = build_graph(pocket_world())
    pairs = {(min(a, b), max(a, b)) for a, b in zip(g.u, g.v)}
    secs = sections(g, pairs)
    mids = sorted(tuple(np.round(m)) for _, m in secs)
    # junctions: the four corners, (150, 0), the pocket's end and the stubs' ends
    assert (75.0, 0.0) in mids and (175.0, 0.0) in mids and (0.0, 50.0) in mids and (150.0, -150.0) in mids and (100.0, 100.0) in mids
    assert len(secs) == 10  # main street 2, verticals 2, parallel 1, pocket 1, stubs 4


def test_spot_on_pocket_street_cuts_the_pocket_off_and_main_street_only_detours():
    from cutdetour import SpotCutter
    g = build_graph(pocket_world())
    src, _ = snap(g, [(0, 0)])
    cutter = SpotCutter(g, src)
    deep, _ = snap(g, [(150, -300)])
    east, _ = snap(g, [(200, 0)])
    d0 = cutter.distances(set())
    assert np.isclose(d0[deep[0]], 450) and np.isclose(d0[east[0]], 200)
    d = cutter.distances(cutter.removed_pairs((150, -75), 10))
    assert np.isinf(d[deep[0]])                      # the pocket has one way out
    d = cutter.distances(cutter.removed_pairs((75, 0), 10))
    assert np.isclose(d[east[0]], 400)               # round by the parallel street: 100 + 200 + 100


def test_spot_removes_parallel_sidewalk_too():
    from cutdetour import SpotCutter
    lines = pocket_world() + [LineString([(25, 4), (125, 4)]), LineString([(25, 0), (25, 4)]),
                              LineString([(125, 0), (125, 4)])]  # a sidewalk 4 m off the main street
    g = build_graph(lines)
    src, _ = snap(g, [(0, 0)])
    cutter = SpotCutter(g, src)
    east, _ = snap(g, [(200, 0)])
    d_line = cutter.distances({p for p in cutter.removed_pairs((75, 0), 1)})   # only the carriageway
    d_spot = cutter.distances(cutter.removed_pairs((75, 0), 10))               # carriageway and sidewalk
    assert d_line[east[0]] < 220 and np.isclose(d_spot[east[0]], 400)


# B8: approaches to a site


def node_at(g, xy):
    n, d = snap(g, [xy], main_only=False)
    assert d[0] < 1e-6, xy
    return int(n[0])


def test_site_at_the_end_of_a_dead_end_street_has_one_approach():
    from cutdetour import approaches, single_gate
    g = build_graph(pocket_world())
    S = [node_at(g, (150, -300))]
    a = approaches(g, S, R=100, L=200, merge_m=20)
    assert a["k_e"] == 1 and a["k"] == 1
    closes, n_skip = single_gate(g, S, R=100, L=200, r=10)
    assert closes and n_skip == 1  # the disk on the site node itself is skipped


def test_site_on_a_through_street_has_two_approaches_cut_near_the_ring():
    from cutdetour import approaches, single_gate
    g = build_graph(pocket_world())
    S = [node_at(g, (75, 0))]
    # with L = 200 the only node 300 m out is the pocket's end; L = 100 puts the parallel street's far corner outside
    a = approaches(g, S, R=100, L=100, merge_m=20)
    # the two edges at the site node touch each other; the cut is taken on the outer side so they stay apart
    assert a["k_e"] == 2 and a["k"] == 2
    closes, _ = single_gate(g, S, R=100, L=100, r=10)
    assert not closes


def test_dead_end_drawn_as_two_parallel_lines_is_one_approach():
    from cutdetour import approaches, single_gate
    lines = pocket_world() + [LineString([(154, -10), (154, -150), (154, -290)]),
                              LineString([(150, 0), (154, -10)]), LineString([(154, -290), (150, -300)])]
    g = build_graph(lines)
    S = [node_at(g, (150, -300))]
    a = approaches(g, S, R=100, L=200, merge_m=20)
    assert a["k_e"] == 2 and a["k"] == 1
    closes, _ = single_gate(g, S, R=100, L=200, r=10)
    assert closes


def test_internal_bottleneck_counts_one():
    """A 30 m stem from the site to a junction, then three streets out."""
    from cutdetour import approaches, single_gate
    lines = [LineString([(0, 0), (30, 0)]),
             LineString([(30, 0), (200, 0), (500, 0)]),
             LineString([(30, 0), (30, 200), (30, 500)]),
             LineString([(30, 0), (30, -200), (30, -500)])]
    g = build_graph(lines)
    S = [node_at(g, (0, 0))]
    a = approaches(g, S, R=100, L=200, merge_m=20)
    assert a["k_e"] == 1 and a["k"] == 1
    closes, _ = single_gate(g, S, R=100, L=200, r=10)
    assert closes


def test_access_nodes_on_two_streets_give_two_approaches():
    from cutdetour import approaches, single_gate
    lines = [LineString([(0, 0), (0, 300), (0, 600)]), LineString([(40, 0), (40, -300), (40, -600)])]
    g = build_graph(lines)
    S = [node_at(g, (0, 0)), node_at(g, (40, 0))]
    a = approaches(g, S, R=100, L=200, merge_m=20)
    assert a["k_e"] == 2 and a["k"] == 2
    closes, _ = single_gate(g, S, R=100, L=200, r=10)
    assert not closes


def test_blockage_over_every_access_node_is_skipped():
    from cutdetour import single_gate
    g = build_graph([LineString([(0, 0), (5, 0), (300, 0), (600, 0)])])
    S = [node_at(g, (0, 0)), node_at(g, (5, 0))]
    closes, n_skip = single_gate(g, S, R=100, L=200, r=10)
    assert n_skip > 0 and closes  # a disk on the long edge still closes the one street
