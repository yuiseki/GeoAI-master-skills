"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_air_residual.py"""

# Tests for pilot_air_residual.py: H3 ring distance (0..15, 16 for farther) from each populated cell to the nearest
# cell with a scheduled-service airport, and its residual given density. Runs with `python -I` in tmp_path on a
# pilot.duckdb holding the tables hexcty, ap (from pilot_air.py) and gdp (from pilot_gtfs.py). The DuckDB h3
# extension must already be installed locally.
#
# Cells: A holds (lat 10, lon 10) and the only scheduled airport; N is one of A's neighbours; R2 is a cell two
# rings from A; F holds (lat -30, lon -60), thousands of km away.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_air_residual.py"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("air_residual")
    c = duckdb.connect(str(d / "pilot.duckdb"))
    c.sql("load h3")
    a = c.sql("select h3_latlng_to_cell_string(10, 10, 4)").fetchall()[0][0]
    ring1 = set(c.sql(f"select h3_grid_disk('{a}', 1)").fetchall()[0][0])
    n = sorted(ring1 - {a})[0]
    r2 = sorted(set(c.sql(f"select h3_grid_disk('{a}', 2)").fetchall()[0][0]) - ring1)[0]
    f = c.sql("select h3_latlng_to_cell_string(-30, -60, 4)").fetchall()[0][0]
    c.execute("create table hexcty(h3 varchar, pop double, a3 varchar)")
    c.executemany("insert into hexcty values (?, ?, ?)",
                  [(a, 1e6, "AAA"), (n, 2e5, "AAA"), (r2, 5e4, "AAA"), (f, 3e4, "FFF"), ("tiny", 500.0, "FFF")])
    c.execute("create table ap(ident varchar, scheduled_service varchar, cell varchar)")
    c.executemany("insert into ap values (?, ?, ?)", [("AP1", "yes", a), ("AP2", "no", f)])
    c.execute("create table gdp(a3 varchar, gdppc double)")
    c.executemany("insert into gdp values (?, ?)", [("AAA", 1000.0), ("FFF", 20000.0)])
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(d / "pilot.duckdb"), read_only=True), r.stdout, (a, n, r2, f)


def test_ring_distance_to_the_nearest_scheduled_airport(run):
    c, _, (a, n, r2, f) = run
    got = dict(c.sql("select h3, k from d2").fetchall())
    assert got == {a: 0, n: 1, r2: 2, f: 16, "tiny": 16}


def test_every_cell_gets_one_distance(run):
    c, out, _ = run
    # cells, cells beyond 15 rings, population 5 or more rings away in millions (F and tiny: 30,500 -> 0)
    assert out.splitlines()[0] == "[(5, 2, 0.0)]"
    assert c.sql("select count(*), count(distinct h3) from dist").fetchall()[0][0] == \
        c.sql("select count(distinct h3) from dist").fetchall()[0][0]


def test_cells_under_1000_people_are_left_out_of_the_model(run):
    c, _, _ = run
    assert c.sql("select count(*) from m").fetchall() == [(4,)]
    assert c.sql("select count(*) from m where h3 = 'tiny'").fetchall() == [(0,)]


def test_residuals_sum_to_zero_around_the_ols_line(run):
    c, _, _ = run
    # r = lk - (a + b * lp) with a, b fitted by least squares over the same rows, so the residuals sum to 0
    assert c.sql("select sum(r) from res").fetchall()[0][0] == pytest.approx(0, abs=1e-9)
