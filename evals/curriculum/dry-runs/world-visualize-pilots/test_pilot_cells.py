"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_cells.py"""

# Tests for pilot_cells.py: share of population in H3 r4 cells with no OpenCelliD record in the cell (gap0) or in
# the cell and its first ring (gap1), against WDI mobile subscriptions. Runs with `python -I` in tmp_path on
# synthetic data/ocid.parquet and data/wdi.parquet and a pilot.duckdb holding table hexcty. The DuckDB h3
# extension must already be installed locally.
#
# Cells: A holds (lat 10, lon 10); N is one of A's neighbours; F holds (lat -30, lon -60). Towers stand only in A.
# Populations: A 1M in AAA, N 2M in BBB, F 3M in FFF.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_cells.py"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("cells")
    (d / "data").mkdir()
    c = duckdb.connect(str(d / "pilot.duckdb"))
    c.sql("load h3")
    a = c.sql("select h3_latlng_to_cell_string(10, 10, 4)").fetchall()[0][0]
    n = sorted(set(c.sql(f"select h3_grid_disk('{a}', 1)").fetchall()[0][0]) - {a})[0]
    f = c.sql("select h3_latlng_to_cell_string(-30, -60, 4)").fetchall()[0][0]
    c.execute("create table hexcty(h3 varchar, pop double, a3 varchar)")
    c.executemany("insert into hexcty values (?, ?, ?)", [(a, 1e6, "AAA"), (n, 2e6, "BBB"), (f, 3e6, "FFF")])
    # updated is unix seconds at noon UTC (the script casts to a date in the local time zone): 2020-09-13, 2023-11-14
    c.sql(f"""copy (select * from (values
        (624, 'LTE', 10.0, 10.0, 1599998400, 5),
        (624, 'GSM', 10.0, 10.0, 1699963200, 1)) t(mcc, radio, lat, lon, updated, samples))
        to '{d}/data/ocid.parquet' (format parquet)""")
    c.sql(f"""copy (select * from (values
        ('AAA', 'IT.CEL.SETS.P2', 2022, 90.0), ('AAA', 'IT.CEL.SETS.P2', 2023, 110.0),
        ('BBB', 'IT.CEL.SETS.P2', 2022, 80.0), ('BBB', 'IT.CEL.SETS.P2', 2023, NULL),
        ('FFF', 'SP.POP.TOTL', 2023, 3e6)) t(country_code, indicator_code, year, value))
        to '{d}/data/wdi.parquet' (format parquet)""")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(d / "pilot.duckdb"), read_only=True), r.stdout, (a, n, f)


def test_towers_are_counted_per_cell_with_the_latest_update(run):
    c, _, (a, _, _) = run
    assert c.sql("select h3, n, last::varchar from oc").fetchall() == [(a, 2, "2023-11-14")]


def test_a_cell_is_covered_by_a_tower_in_it_or_in_its_first_ring(run):
    c, _, (a, n, f) = run
    got = {h: (k, ring) for h, k, ring in c.sql("select h3, n, ring1 from cov").fetchall()}
    assert got == {a: (2, True), n: (0, True), f: (0, False)}


def test_population_without_coverage(run):
    c, out, _ = run
    # no tower in the cell: N and F = 5M; none in the ring either: F = 3M
    assert "[(5.0, 3.0)]" in out
    got = {a3: (g0, g1) for a3, g0, g1 in c.sql("select a3, gap0, gap1 from gap").fetchall()}
    assert got["BBB"][0] == 1.0 and got["FFF"] == (1.0, 1.0)


def test_a_fully_covered_country_has_a_gap_of_zero(run):
    c, _, _ = run
    got = {a3: (g0, g1) for a3, g0, g1 in c.sql("select a3, gap0, gap1 from gap").fetchall()}
    assert got == {"AAA": (0.0, 0.0), "BBB": (1.0, 0.0), "FFF": (1.0, 1.0)}


def test_subscriptions_take_the_latest_non_null_year(run):
    c, _, _ = run
    assert sorted(c.sql("select a3, cel, y from w").fetchall()) == [("AAA", 110.0, 2023), ("BBB", 80.0, 2022)]
