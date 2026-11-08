"""uvx --python 3.12 --with numpy --with pandas --with pyproj --with scipy --with pytest pytest -q -p no:cacheprovider test_compute_allocations.py"""

import numpy as np
import pandas as pd
import pytest
from scipy.spatial import cKDTree

from compute_allocations import KEY_MESHES, clean, distance_to_nodes, ranking, summarize, top_codes


def test_clean_turns_non_finite_into_none_and_numpy_into_python():
    out = clean({"a": [np.float64(1.5), np.int64(2), float("nan")], "b": (np.float32(np.inf), "x")})
    assert out == {"a": [1.5, 2, None], "b": [None, "x"]}
    assert type(out["a"][1]) is int


def test_distance_to_nodes_adds_the_snap_offset_and_drops_far_points():
    tree = cKDTree(np.array([[0.0, 0.0], [100.0, 0.0]]))
    node_distance = np.array([250.0, np.inf])                 # node 1 cannot reach any stop
    points = np.array([[30.0, 40.0], [100.0, 10.0], [0.0, 600.0]])
    out, raw = distance_to_nodes(tree, node_distance, points, 500)
    # point 0 snaps 50 m to node 0 -> 300; point 1 snaps to node 1 (inf) -> NaN; point 2 is 600 m away -> NaN
    assert out[0] == pytest.approx(300.0) and np.isnan(out[1]) and np.isnan(out[2])
    assert raw.tolist() == pytest.approx([50.0, 10.0, 600.0])
    out200, _ = distance_to_nodes(tree, node_distance, points[:1], 40)
    assert np.isnan(out200[0])                                 # 50 m snap > 40 m limit


FRAME = pd.DataFrame({
    "mesh": [KEY_MESHES[0], "m2", "m3", "m4"],
    "x": [10.0, 30.0, 30.0, 0.0],
    "y": [40.0, 20.0, np.nan, 10.0],
})


def test_ranking_and_top_codes_skip_zero_and_missing():
    assert ranking(FRAME, "x").mesh.tolist() == ["m2", "m3", KEY_MESHES[0]]
    assert top_codes(FRAME, "y", n=2) == [KEY_MESHES[0], "m2"]


def test_summarize_overlaps_totals_and_key_positions():
    r = summarize(FRAME, {"x": "x", "y": "y"}, "t")
    assert r["totals"] == {"x": 70.0, "y": 70.0}
    assert r["positive_meshes"] == {"x": 3, "y": 3}
    assert r["overlaps"]["x__y"] == 2                          # {m2, m3, key} & {key, m2, m4}
    assert r["top10_intersection_all"] == sorted([KEY_MESHES[0], "m2"])
    assert r["key_mesh_positions"][KEY_MESHES[0]] == {"x": 3, "y": 1}
    assert r["key_mesh_positions"][KEY_MESHES[1]] == {"x": None, "y": None}
    # Spearman over rows complete in both columns (key, m2, m4): x = [10, 30, 0], y = [40, 20, 10] -> 0.5
    assert r["spearman"]["x__y"] == pytest.approx(0.5)
