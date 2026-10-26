"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with pandas --with pyarrow --with pytest pytest test_grid_distance.py

Expected values are worked out by hand on small grids; the distance is checked against a brute force with scipy's cKDTree.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString

import grid_distance as gd

HERE = Path(__file__).parent


def test_a_straight_line_marks_its_row_only():
    pres = gd.line_presence(gd.GridSpec(0, 0, 10, 3, 100), [LineString([(5, 150), (995, 150)])])
    assert pres[1].all() and not pres[0].any() and not pres[2].any()


def test_a_long_diagonal_segment_skips_no_cell():
    pres = gd.line_presence(gd.GridSpec(0, 0, 10, 10, 100), [LineString([(5, 5), (995, 995)])])
    assert all(pres[i, i] for i in range(10))


def test_distance_by_hand_and_nan_without_features():
    pres = np.zeros((5, 5), dtype=bool)
    pres[2, 2] = True
    d = gd.distance_m(pres, 100.0)
    assert d[2, 2] == 0 and d[2, 4] == 200 and np.isclose(d[0, 0], np.hypot(200, 200))
    assert np.isnan(gd.distance_m(np.zeros((3, 3), dtype=bool), 100.0)).all()


def test_distance_matches_a_brute_force_nearest_cell():
    from scipy.spatial import cKDTree

    rng = np.random.default_rng(0)
    pres = rng.random((40, 50)) < 0.01
    d = gd.distance_m(pres, 100.0)
    fy, fx = np.nonzero(pres)
    yy, xx = np.mgrid[0:40, 0:50]
    nearest, _ = cKDTree(np.column_stack([fx, fy]) * 100.0).query(np.column_stack([xx.ravel(), yy.ravel()]) * 100.0)
    assert np.allclose(d.ravel(), nearest)


def test_padding_lets_a_feature_across_the_edge_count():
    g = gd.GridSpec(0, 0, 10, 10, 100)
    line = [LineString([(-150, -500), (-150, 1500)])]  # 1.5 cells west of the grid
    pg = gd.padded(g, 5)
    d = gd.crop(gd.distance_m(gd.line_presence(pg, line), 100.0), 5, g)
    assert d[5, 0] == 200  # from the first column (centre x = 50) to the cell at x = -150
    assert gd.line_presence(g, line).sum() == 0  # without the margin the line is not seen at all


def test_command_line_with_points_and_lines(tmp_path):
    import pandas as pd

    wkb = [shapely.to_wkb(LineString([(0, 50), (1000, 50)])), shapely.to_wkb(shapely.Point(550, 950)), shapely.to_wkb(shapely.Point(560, 960))]
    pd.DataFrame({"geom": wkb, "kind": ["road", "building", "building"]}).to_parquet(tmp_path / "f.parquet")
    json.dump({"x0": 0, "y0": 0, "nx": 10, "ny": 10, "size": 100, "crs": "EPSG:6678"}, open(tmp_path / "g.json", "w"))
    r = subprocess.run([sys.executable, str(HERE / "grid_distance.py"), str(tmp_path / "f.parquet"), "geom", "EPSG:6678",
                        str(tmp_path / "g.json"), str(tmp_path / "o.npz"), "--where", "kind = 'building'", "--pad", "2"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    o = np.load(tmp_path / "o.npz")
    assert o["count"][9, 5] == 2 and o["distance"][9, 5] == 0 and o["distance"][0, 5] == 900
