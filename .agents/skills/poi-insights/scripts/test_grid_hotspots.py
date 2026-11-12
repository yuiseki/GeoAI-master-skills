"""uvx --with h3 --with s2sphere --with numpy --with scipy --with pytest pytest test_grid_hotspots.py"""

# Tests for grid_hotspots.py: points to H3 or S2 cells, Getis-Ord Gi* over every cell of the study area (zeros
# included), Benjamini-Hochberg on the one-sided p-values, and clusters as connected hot cells ranked by points.

import math

import h3
import numpy as np
import pytest

from grid_hotspots import assign, bh_reject, clusters, gi_star, hotspots, study_cells


def test_points_fall_in_the_cell_that_contains_them():
    lon, lat = -0.1276, 51.5072
    c = assign([lon], [lat], "h3", 9)[0]
    assert c == h3.latlng_to_cell(lat, lon, 9)
    assert h3.cell_to_latlng(c) == pytest.approx((lat, lon), abs=0.003)
    s = assign([lon], [lat], "s2", 14)[0]
    import s2sphere
    cell = s2sphere.Cell(s2sphere.CellId.from_token(s))
    assert cell.contains(s2sphere.LatLng.from_degrees(lat, lon).to_point())
    assert s2sphere.CellId.from_token(s).level() == 14


def test_gi_star_by_hand():
    # Four cells on a line, binary weights with self: neighbours of i are i-1, i, i+1.
    x = np.array([0.0, 0.0, 6.0, 2.0])
    nb = {0: [0, 1], 1: [0, 1, 2], 2: [1, 2, 3], 3: [2, 3]}
    z = gi_star(x, nb)
    n, xbar = 4, 2.0
    s = math.sqrt((x ** 2).sum() / n - xbar ** 2)
    w = 3
    expect = (8.0 - xbar * w) / (s * math.sqrt((n * w - w * w) / (n - 1)))
    assert z[2] == pytest.approx(expect)


def test_bh_controls_the_list_not_each_test():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.6])
    assert bh_reject(p, 0.05).tolist() == [True, True, False, False, False]


def test_clusters_are_connected_hot_cells_ranked_by_points():
    a = h3.latlng_to_cell(51.5, -0.1, 9)
    ring = list(h3.grid_ring(a, 1))
    far = h3.latlng_to_cell(51.6, 0.1, 9)
    counts = {a: 10, ring[0]: 5, far: 3}
    got = clusters({a, ring[0], far}, counts, "h3")
    assert [c["cells"] for c in got] == [2, 1] and [c["points"] for c in got] == [15, 3]


def test_a_dense_block_in_a_quiet_area_is_one_cluster():
    rng = np.random.default_rng(1)
    centre = (51.50, -0.12)
    # 300 points spread over ~10 km, 150 more inside ~150 m.
    lat = np.r_[rng.uniform(51.45, 51.55, 300), rng.normal(centre[0], 0.0008, 150)]
    lon = np.r_[rng.uniform(-0.20, -0.04, 300), rng.normal(centre[1], 0.0012, 150)]
    res = hotspots(lon, lat, "h3", 9, bbox=(-0.20, 51.45, -0.04, 51.55))
    top = res["clusters"][0]
    assert top["points"] >= 120
    assert h3.great_circle_distance((top["lat"], top["lon"]), centre, unit="m") < 400
    assert res["audit"]["points"] == 450 and res["audit"]["outside"] == 0
    assert res["audit"]["cells"] >= len(study_cells((-0.20, 51.45, -0.04, 51.55), 9))


def test_points_outside_the_study_area_are_counted_not_used():
    res = hotspots([-0.1, 5.0], [51.5, 51.5], "h3", 8, bbox=(-0.2, 51.4, 0.0, 51.6))
    assert res["audit"]["outside"] == 1


def test_uniform_points_give_no_cluster_most_of_the_time():
    rng = np.random.default_rng(2)
    lat, lon = rng.uniform(51.45, 51.55, 2000), rng.uniform(-0.2, -0.04, 2000)
    res = hotspots(lon, lat, "h3", 8, bbox=(-0.2, 51.45, -0.04, 51.55))
    assert len(res["clusters"]) <= 1
