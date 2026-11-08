"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_conflict.py"""

# Tests for pilot_conflict.py: population in H3 r4 cells within k rings of lethal UCDP GED events of 2021-2025,
# for all events and for precisely located ones. Runs with `python -I` in tmp_path on a synthetic
# data/ucdp.parquet and a pilot.duckdb holding table hexcty. The DuckDB h3 extension must already be installed.
#
# Cells: A holds (lat 10, lon 10); N is one of A's six neighbours; F holds (lat -30, lon -60), far from both.
# Populations: A 1M in AAA, N 2M in BBB, F 3M in FFF.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_conflict.py"


def cells():
    c = duckdb.connect()
    c.sql("load h3")
    a = c.sql("select h3_latlng_to_cell_string(10, 10, 4)").fetchall()[0][0]
    n = sorted(set(c.sql(f"select h3_grid_disk('{a}', 1)").fetchall()[0][0]) - {a})[0]
    f = c.sql("select h3_latlng_to_cell_string(-30, -60, 4)").fetchall()[0][0]
    centre = {h: c.sql(f"select h3_cell_to_lat('{h}'), h3_cell_to_lng('{h}')").fetchall()[0] for h in (a, n, f)}
    return a, n, f, centre


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("conflict")
    (d / "data").mkdir()
    a, n, f, centre = cells()
    c = duckdb.connect(str(d / "pilot.duckdb"))
    c.execute("create table hexcty(h3 varchar, pop double, a3 varchar)")
    c.executemany("insert into hexcty values (?, ?, ?)", [(a, 1e6, "AAA"), (n, 2e6, "BBB"), (f, 3e6, "FFF")])
    events = [  # id, year, where_prec, best, country_id, cell
        (1, 2022, 1, 5, 100, a),
        (2, 2025, 4, 2, 200, f),     # coarse position
        (3, 2019, 1, 9, 100, n),     # before 2021
        (4, 2023, 1, 0, 100, n),     # nobody killed
    ]
    rows = [(i, y, p, b, cid, *centre[h]) for i, y, p, b, cid, h in events]
    c.execute("create table u(id int, year int, where_prec int, best int, country_id int, latitude double, longitude double)")
    c.executemany("insert into u values (?, ?, ?, ?, ?, ?, ?)", rows)
    c.sql(f"copy u to '{d}/data/ucdp.parquet' (format parquet)")
    c.sql("drop table u")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(d / "pilot.duckdb"), read_only=True), r.stdout, (a, n, f)


def table(c, name):
    return dict(c.sql(f"select a3, pop_m from {name}").fetchall())


def test_only_lethal_events_of_2021_to_2025_are_kept(run):
    c, out, _ = run
    assert sorted(r[0] for r in c.sql("select id from ev").fetchall()) == [1, 2]
    # events, deaths, precise events, precise deaths
    assert out.splitlines()[0] == "[(2, 7, 1, 5)]"


def test_the_event_cell_is_its_h3_r4_cell(run):
    c, _, (a, n, f) = run
    assert dict(c.sql("select id, cell from ev").fetchall()) == {1: a, 2: f}


def test_k0_counts_the_event_cells_and_k1_adds_the_ring(run):
    c, _, _ = run
    assert table(c, "c_all_0") == {"AAA": 1.0, "FFF": 3.0}
    assert table(c, "c_all_1") == {"AAA": 1.0, "BBB": 2.0, "FFF": 3.0}


def test_precise_events_only(run):
    c, _, _ = run
    assert table(c, "c_prec2_0") == {"AAA": 1.0}
    assert table(c, "c_prec2_1") == {"AAA": 1.0, "BBB": 2.0}


def test_a_cell_reached_from_two_events_is_counted_once(tmp_path):
    a, n, f, centre = cells()
    (tmp_path / "data").mkdir()
    c = duckdb.connect(str(tmp_path / "pilot.duckdb"))
    c.execute("create table hexcty(h3 varchar, pop double, a3 varchar)")
    c.executemany("insert into hexcty values (?, ?, ?)", [(a, 1e6, "AAA"), (n, 2e6, "BBB")])
    c.sql(f"""copy (select * from (values (1, 2022, 1, 1, 1, {centre[a][0]}, {centre[a][1]}),
                                          (2, 2022, 1, 1, 1, {centre[n][0]}, {centre[n][1]}))
                    t(id, year, where_prec, best, country_id, latitude, longitude))
              to '{tmp_path}/data/ucdp.parquet' (format parquet)""")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    c = duckdb.connect(str(tmp_path / "pilot.duckdb"), read_only=True)
    assert table(c, "c_all_1") == {"AAA": 1.0, "BBB": 2.0}
