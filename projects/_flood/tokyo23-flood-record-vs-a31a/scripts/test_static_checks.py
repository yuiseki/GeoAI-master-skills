"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with numpy --with scikit-learn --with shapely --with pyproj --with pytest pytest -q -p no:cacheprovider test_static_checks.py"""

# load and history of 03_static.py, morans_i_lag of 09_checks.py, square of 11_spatial_maps.py.
import importlib

import duckdb
import numpy as np
import pytest

st = importlib.import_module("03_static")
ck = importlib.import_module("09_checks")
sm = importlib.import_module("11_spatial_maps")


def test_morans_i_lag_on_an_alternating_row():
    v = np.array([1.0, 0.0, 1.0, 0.0])
    ix, iy = np.arange(4), np.zeros(4, int)
    # lag 1: three neighbour pairs of opposite sign, -0.25 each: I = 4/3 * (-0.75) / 1 = -1
    assert ck.morans_i_lag(v, ix, iy, 1) == (pytest.approx(-1.0), 3)
    # lag 2: pairs (0, 2) and (1, 3), +0.25 each: I = 4/2 * 0.5 / 1 = 1
    assert ck.morans_i_lag(v, ix, iy, 2) == (pytest.approx(1.0), 2)


def test_morans_i_lag_counts_rows_and_columns_and_skips_empty_cells():
    # 2 x 2 block with one cell missing from the grid (ix, iy list only 3 cells)
    v = np.array([2.0, 0.0, 1.0])
    ix, iy = np.array([0, 1, 0]), np.array([0, 0, 1])
    # z = [1, -1, 0]; pairs: (0,0)-(1,0) row: 1 * -1; (0,0)-(0,1) column: 1 * 0 -> num -1, w 2; sum z^2 = 2
    assert ck.morans_i_lag(v, ix, iy, 1) == (pytest.approx(3 / 2 * -1 / 2), 2)


def test_history_weights_each_year_by_its_flooded_cells():
    cells = {"ix": np.array([0, 1, 2]), "iy": np.array([0, 0, 0])}
    ids, years = np.array([0, 1, 1]), np.array([2000, 2000, 2001])
    h = st.history(cells, ids, years, 100)
    assert h["h_cell"].tolist() == [0.5, 1.5, 0.0]
    assert h["h_300"].tolist() == [2.0, 2.0, 2.0]          # radius round(150 / 100) = 2 covers the whole row
    h150 = st.history(cells, ids, years, 150)
    assert h150["h_300"].tolist() == [2.0, 2.0, 1.5]       # radius 1


def test_load_splits_periods_and_filters_label_and_reason(tmp_path):
    con = duckdb.connect()
    con.execute(f"copy (select * from (values (0, 0), (1, 0), (2, 0)) t(ix, iy)) to '{tmp_path / 'cells.parquet'}'")
    con.execute(f"""copy (select * from (values
        (0, 1980, 2, true, true, false),
        (1, 1990, 1, false, false, true),
        (1, 2000, 3, true, true, false),
        (2, 2010, 1, true, false, true),
        (2, 2020, 5, true, true, false)) t(cell, year, n_poly, centre_in, naisui, issui))
        to '{tmp_path / 'flood_cell_year.parquet'}'""")
    cells, (ptr, ctr, idtr, ytr), (pte, cte, idte, yte) = st.load(tmp_path, (1974, 1996), (1997, 2019), "any", "all")
    assert len(cells["ix"]) == 3
    assert ptr.tolist() == [True, True, False] and ctr.tolist() == [2.0, 1.0, 0.0]
    assert pte.tolist() == [False, True, True] and cte.tolist() == [0.0, 3.0, 1.0]   # 2020 is outside the test period
    assert sorted(ytr.tolist()) == [1980, 1990]
    _, (ptr, _, _, _), (pte, _, _, _) = st.load(tmp_path, (1974, 1996), (1997, 2019), "centre", "naisui")
    assert ptr.tolist() == [True, False, False] and pte.tolist() == [False, True, False]


def test_square_is_a_closed_ring_of_one_cell():
    ring = sm.square(1000.0, 2000.0)["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) == 5
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    assert max(xs) - min(xs) == sm.SIZE and max(ys) - min(ys) == sm.SIZE
    assert (max(xs) + min(xs)) / 2 == 1000.0
