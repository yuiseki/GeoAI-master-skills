"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_refugee.py"""

# Tests for pilot_refugee.py: refugees hosted in 2025 by count, per person and per GDP, and the share hosted in
# a bordering country. Runs with `python -I` in tmp_path on synthetic data/unhcr.parquet, data/ne0.parquet and
# data/wdi.parquet. The DuckDB spatial extension must already be installed locally.
#
# Countries: AAA lon 0..10 and BBB lon 10..20 share a border; CCC lon 40..50 touches nobody. XXX is an origin
# that is not on the map. Natural Earth's '-99' rows are left out.

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_refugee.py"

COUNTRIES = [
    ("AAA", "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))"),
    ("BBB", "POLYGON((10 0, 20 0, 20 10, 10 10, 10 0))"),
    ("CCC", "POLYGON((40 0, 50 0, 50 10, 40 10, 40 0))"),
    ("-99", "POLYGON((20 0, 30 0, 30 10, 20 10, 20 0))"),
]
UNHCR = [  # Year, origin, asylum, refugees
    (2025, "AAA", "BBB", 1000),   # to a neighbour
    (2025, "AAA", "CCC", 500),
    (2025, "BBB", "AAA", 300),    # to a neighbour
    (2025, "XXX", "CCC", 200),    # origin not on the map
    (2025, "CCC", "AAA", 0),      # no refugees: dropped
    (2024, "AAA", "CCC", 9999),   # another year: dropped
]
WDI = [  # country_code, indicator_code, year, value
    ("AAA", "SP.POP.TOTL", 2024, 1e7), ("AAA", "SP.POP.TOTL", 2020, 1.0),
    ("BBB", "SP.POP.TOTL", 2024, 2e6),
    ("CCC", "SP.POP.TOTL", 2024, 5e5),
    ("AAA", "NY.GDP.MKTP.PP.CD", 2024, 1e11),
    ("BBB", "NY.GDP.MKTP.PP.CD", 2023, 1e9), ("BBB", "NY.GDP.MKTP.PP.CD", 2024, None),
    ("CCC", "NY.GDP.MKTP.PP.CD", 2024, 1e10),
]


def printed(out, label):
    line = next(l for l in out.splitlines() if l.startswith(label + " "))
    return eval(line[len(label) + 1:], {"Decimal": Decimal})


@pytest.fixture
def db(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    c = duckdb.connect()
    c.sql("load spatial")
    c.execute("create table ne(iso3 varchar, wkt varchar)")
    c.executemany("insert into ne values (?, ?)", COUNTRIES)
    c.sql(f"copy (select iso3 ISO_A3_EH, ST_GeomFromText(wkt) geometry from ne) to '{d}/ne0.parquet' (format parquet)")
    c.execute("create table u(y int, o varchar, a varchar, r bigint)")
    c.executemany("insert into u values (?, ?, ?, ?)", UNHCR)
    c.sql(f"""copy (select y "Year", o "Country of origin (ISO)", a "Country of asylum (ISO)",
              r "Refugees under UNHCR's mandate" from u) to '{d}/unhcr.parquet' (format parquet)""")
    c.execute("create table w(country_code varchar, indicator_code varchar, year int, value double)")
    c.executemany("insert into w values (?, ?, ?, ?)", WDI)
    c.sql(f"copy w to '{d}/wdi.parquet' (format parquet)")
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(tmp_path / "pilot.duckdb"), read_only=True), r.stdout


def test_neighbours_are_pairs_of_countries_that_touch_both_ways(db):
    c, _ = db
    assert sorted(c.sql("select x, y from nb").fetchall()) == [("AAA", "BBB"), ("BBB", "AAA")]


def test_only_2025_rows_with_refugees_are_used(db):
    c, out = db
    assert sorted(c.sql("select o, a, r from rf").fetchall()) == [
        ("AAA", "BBB", 1000), ("AAA", "CCC", 500), ("BBB", "AAA", 300), ("XXX", "CCC", 200)]


def test_neighbour_share_and_unmatched_share(db):
    _, out = db
    # neighbours: (1000 + 300) / 2000; not on the map: 200 / 2000
    assert printed(out, "neighbour share") == [(0.65, 0.1)]


def test_host_table_takes_the_latest_non_null_indicator(db):
    c, _ = db
    got = {a: (r, pop, gdp) for a, r, pop, gdp in c.sql("select iso3, r, pop, gdp from host").fetchall()}
    assert got == {"BBB": (1000, 2e6, 1e9), "CCC": (700, 5e5, 1e10), "AAA": (300, 1e7, 1e11)}


def test_rankings(db):
    _, out = db
    assert printed(out, "by count") == [(["BBB", "CCC", "AAA"],)]
    # countries of a million people or fewer are left out of the per-person and per-GDP rankings
    assert printed(out, "per 1000 pop") == [(["BBB", "AAA"],)]
    assert printed(out, "per GDP") == [(["BBB", "AAA"],)]
