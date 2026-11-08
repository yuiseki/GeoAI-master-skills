"""uvx --python 3.12 --with 'duckdb>=1.5.5,<2' --with scikit-learn --with pandas --with pyarrow --with numpy --with pytest pytest -q docs/tutorial/test_points.py"""

# Tests for points.py: events -> 100 km cells in EPSG:6933 -> features -> CV by 1,000 km blocks.
# The script reads UCDP GED from Hugging Face. Here duckdb.connect is wrapped so the hf:// URL points at a
# small synthetic GeoParquet in tmp_path and `install httpfs` is skipped; nothing goes to the network.
# The DuckDB spatial extension must already be installed locally (`load spatial` only).
# DuckDB is held below 2: in the 2.0 Python API a relation has no fetchone(), and points.py calls
# con.sql(...).fetchone(), so under the `duckdb>=1.5.5` of the tutorial's own command it stops at line 31.
#
# Where the synthetic events land: EPSG:6933 is cylindrical equal-area with standard parallels +-30,
# so x = a * k0 * lon_rad with a = 6378137 and k0 = cos 30 / sqrt(1 - e^2 sin^2 30) = 0.86675,
# i.e. 96,487 m per degree of longitude. At lat 0.5 y is about 64 km, so every point is in row cy = 0.
#   lon   0.5 -> x =    48,243 -> cx =   0, block  0
#   lon   1.5 -> x =   144,730 -> cx =   1, block  0
#   lon   2.5 -> x =   241,216 -> cx =   2, block  0
#   lon  30.5 -> x = 2,942,839 -> cx =  29, block  2
#   lon  60.5 -> x = 5,837,439 -> cx =  58, block  5
#   lon -30.5 -> x = -2,942,839 -> cx = -30, block -3
#   lon -60.5 -> x = -5,837,439 -> cx = -59, block -6

import runpy
from pathlib import Path

import duckdb
import numpy as np
import pytest

SCRIPT = Path(__file__).parent / "points.py"
HF = "hf://datasets/yuiseki/ucdp-ged/parquet/26.1/ged.parquet"
REAL_CONNECT = duckdb.connect

# (lon, year, where_prec, how many events)
EVENTS = [
    (0.5, 2022, 1, 3), (0.5, 2023, 1, 2),
    (1.5, 2022, 2, 1), (1.5, 2023, 1, 4),
    (2.5, 2022, 1, 2),
    (30.5, 2022, 1, 1), (30.5, 2023, 2, 1),
    (60.5, 2022, 1, 5), (60.5, 2023, 1, 5),
    (-30.5, 2022, 2, 2),
    (-60.5, 2022, 1, 1), (-60.5, 2023, 1, 3),
    # dropped: coarse position, or a year outside 2022-2023
    (0.5, 2022, 3, 10), (1.5, 2023, 4, 10), (2.5, 2021, 1, 10), (30.5, 2024, 1, 10),
    # a cell with 2023 events only (cx = 3): not a row, but its 2022 count of 0 is a neighbour's
    (3.5, 2023, 1, 6),
]


def write_ged(path):
    rows = [(lon, year, prec) for lon, year, prec, n in EVENTS for _ in range(n)]
    con = duckdb.connect()
    con.sql("load spatial")
    con.execute("create table ged(lon double, year int, where_prec int)")
    con.executemany("insert into ged values (?, ?, ?)", rows)
    con.sql(f"copy (select year, where_prec, ST_Point(lon, 0.5) as geometry from ged) to '{path}' (format parquet)")


class LocalCon:
    def __init__(self, local):
        self.con, self.local = REAL_CONNECT(), local

    def sql(self, q):
        if q.strip().startswith("install httpfs"):
            q = "load spatial"
        return self.con.sql(q.replace(HF, self.local))


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("points")
    write_ged(d / "ged.parquet")
    duckdb.connect = lambda *a, **k: LocalCon(str(d / "ged.parquet"))
    try:
        g = runpy.run_path(str(SCRIPT), run_name="points")
    finally:
        duckdb.connect = REAL_CONNECT
    return g


def test_only_precise_events_of_2022_and_2023_are_counted(run):
    # 3+2+1+4+2+1+1+5+5+2+1+3+6 = 36
    assert run["n_events"] == 36


def test_one_row_per_cell_with_a_2022_event(run):
    t = run["t"].set_index("cx")
    assert sorted(t.index) == [-59, -30, 0, 1, 2, 29, 58]
    assert (run["t"]["cy"] == 0).all()
    assert t.loc[0, ["n22", "n23"]].tolist() == [3, 2]
    assert t.loc[1, ["n22", "n23"]].tolist() == [1, 4]
    assert t.loc[2, ["n22", "n23"]].tolist() == [2, 0]
    assert t.loc[-30, ["n22", "n23"]].tolist() == [2, 0]


def test_neighbours_sum_the_2022_events_of_the_eight_surrounding_cells(run):
    nb = run["t"].set_index("cx")["nb22"]
    assert nb[0] == 1        # cell 1
    assert nb[1] == 3 + 2    # cells 0 and 2, not itself
    assert nb[2] == 1 + 0    # cell 1 and cell 3, which had 2023 events only
    assert nb[29] == 0 and nb[58] == 0 and nb[-30] == 0 and nb[-59] == 0


def test_cv_blocks_are_1000_km_squares(run):
    blocks = dict(zip(run["t"]["cx"], run["block"]))
    assert blocks[0] == blocks[1] == blocks[2] == "0_0"
    assert blocks[29] == "2_0" and blocks[58] == "5_0"
    assert blocks[-30] == "-3_0" and blocks[-59] == "-6_0"
    assert run["block"].nunique() == 5


def test_target_and_features_are_log1p_counts(run):
    t = run["t"]
    assert np.allclose(run["y"], np.log1p(t["n23"]))
    assert np.allclose(run["base"][:, 0], np.log1p(t["n22"]))
    assert np.allclose(run["base"][:, 1], np.log1p(t["nb22"]))
    assert np.array_equal(run["with_xy"][:, 2:], t[["cx", "cy"]].to_numpy())


def test_every_scheme_and_model_gets_an_r2(run):
    assert len(run["schemes"]) == 2 and len(run["models"]) == 4
    assert all(r.startswith("R2 ") for r in run["row"])
    assert len(run["row"]) == 4


def test_a_parquet_without_where_prec_fails_loudly(tmp_path):
    con = duckdb.connect()
    con.sql("load spatial")
    con.sql(f"copy (select 2022 as year, ST_Point(0.5, 0.5) as geometry) to '{tmp_path / 'ged.parquet'}' (format parquet)")
    duckdb.connect = lambda *a, **k: LocalCon(str(tmp_path / "ged.parquet"))
    try:
        with pytest.raises(duckdb.Error, match="where_prec"):
            runpy.run_path(str(SCRIPT), run_name="points")
    finally:
        duckdb.connect = REAL_CONNECT
