"""uvx --from 'duckdb>=1.5.5' --with shapely --with numpy --with pyarrow --with pytest pytest test_contiguity.py

A 3 x 3 grid of unit squares, numbered row by row:
    0 1 2
    3 4 5
    6 7 8
Queen (any shared point): centre 8, corners 3, edge middles 5. Rook (a shared edge): 4, 2, 3.
"""

import shapely

from contiguity import components, contiguity

GRID = [shapely.box(c, -r, c + 1, -r + 1) for r in range(3) for c in range(3)]


def test_queen_and_rook_by_hand():
    q = contiguity(GRID, "queen")
    r = contiguity(GRID, "rook")
    assert [len(q[i]) for i in range(9)] == [3, 5, 3, 5, 8, 5, 3, 5, 3]
    assert [len(r[i]) for i in range(9)] == [2, 3, 2, 3, 4, 3, 2, 3, 2]
    assert sorted(r[4]) == [1, 3, 5, 7] and 0 in q[4] and 0 not in r[4]
    assert all(i in q[j] for i in range(9) for j in q[i])          # symmetric


def test_a_hairline_gap_breaks_adjacency_unless_a_tolerance_is_given():
    a, b = shapely.box(0, 0, 1, 1), shapely.box(1 + 1e-9, 0, 2, 1)
    assert contiguity([a, b], "rook") == {0: [], 1: []}
    assert contiguity([a, b], "rook", tolerance=1e-6) == {0: [1], 1: [0]}


def test_an_overlapping_border_still_counts_as_a_shared_edge():
    a, b = shapely.box(0, 0, 1, 1), shapely.box(0.9999, 0, 2, 1)     # overlaps by 1e-4 instead of touching
    assert contiguity([a, b], "rook") == {0: [1], 1: [0]}


def test_islands_and_components_are_counted():
    shapes = GRID[:2] + [shapely.box(10, 10, 11, 11)]               # two neighbours and an island
    nb = contiguity(shapes, "queen")
    assert nb[2] == []
    assert components(nb) == [[0, 1], [2]]
