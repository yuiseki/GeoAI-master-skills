"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_base2.py"""

# Tests for base2.py: assign each hexagon centroid of table `hex` to the Natural Earth country containing it,
# or the nearest one when none does, giving table `hexcty`. Runs with `python -I` in tmp_path on a synthetic
# pilot.duckdb (table hex) and data/ne0.parquet. The DuckDB spatial extension must already be installed locally.
#
# Countries: AAA is the square lon 0..10, lat 0..10; BBB is lon 10..20, lat 0..10 (they share the line lon 10).
# Distances are planar degrees.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "base2.py"

COUNTRIES = [  # ADM0_A3, ISO_A3_EH, NAME_JA, wkt
    ("AAA", "AAA", "エー", "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))"),
    ("BBB", "BBB", "ビー", "POLYGON((10 0, 20 0, 20 10, 10 10, 10 0))"),
]
HEXES = [  # h3, pop, lon, lat
    ("h_in_a", 100.0, 5, 5),
    ("h_in_b", 200.0, 15, 5),
    ("h_sea_near_b", 50.0, 25, 5),   # 5 from BBB, 15 from AAA
    ("h_sea_near_a", 30.0, -3, 5),   # 3 from AAA
]


def setup(d: Path, hexes=HEXES):
    (d / "data").mkdir()
    c = duckdb.connect(str(d / "pilot.duckdb"))
    c.sql("load spatial")
    c.execute("create table nek(a3 varchar, iso3 varchar, name_ja varchar, wkt varchar)")
    c.executemany("insert into nek values (?, ?, ?, ?)", COUNTRIES)
    c.sql(f"""copy (select a3 ADM0_A3, iso3 ISO_A3_EH, name_ja NAME_JA, ST_GeomFromText(wkt) geometry from nek)
              to '{d}/data/ne0.parquet' (format parquet)""")
    c.sql("drop table nek")
    c.execute("create table hx(h3 varchar, pop double, lon double, lat double)")
    c.executemany("insert into hx values (?, ?, ?, ?)", hexes)
    c.sql("create table hex as select h3, pop, ST_Point(lon, lat) ctr from hx")
    c.sql("drop table hx")
    c.close()


def run(d: Path):
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    c = duckdb.connect(str(d / "pilot.duckdb"), read_only=True)
    c.sql("load spatial")
    return c, r.stdout


def test_a_centroid_inside_a_country_takes_that_country(tmp_path):
    setup(tmp_path)
    c, _ = run(tmp_path)
    got = dict(c.sql("select h3, a3 from hexcty where not nearest").fetchall())
    assert got == {"h_in_a": "AAA", "h_in_b": "BBB"}


def test_a_centroid_at_sea_takes_the_nearest_country_and_is_flagged(tmp_path):
    setup(tmp_path)
    c, _ = run(tmp_path)
    got = dict(c.sql("select h3, a3 from hexcty where nearest").fetchall())
    assert got == {"h_sea_near_b": "BBB", "h_sea_near_a": "AAA"}
    assert dict(c.sql("select h3, d from hexn").fetchall()) == {"h_sea_near_b": 5.0, "h_sea_near_a": 3.0}


def test_every_hexagon_is_kept_once_with_its_population(tmp_path):
    setup(tmp_path)
    c, out = run(tmp_path)
    assert c.sql("select count(*), count(distinct h3), sum(pop) from hexcty").fetchall() == [(4, 4, 380.0)]
    # first summary line: count, distinct, unassigned population in millions, unassigned hexagons
    assert out.splitlines()[0] == "[(4, 4, 8e-05, 2)]"


def test_a_centroid_on_a_shared_border_is_counted_once(tmp_path):
    setup(tmp_path, HEXES + [("h_border", 1000.0, 10, 5)])
    c, _ = run(tmp_path)
    assert c.sql("select count(*), count(distinct h3), sum(pop) from hexcty").fetchall() == [(5, 5, 1380.0)]


def test_without_the_hex_table_it_fails(tmp_path):
    (tmp_path / "data").mkdir()
    setup_dir = tmp_path
    c = duckdb.connect(str(setup_dir / "pilot.duckdb"))
    c.sql("load spatial")
    c.sql(f"copy (select 'AAA' ADM0_A3, 'AAA' ISO_A3_EH, 'エー' NAME_JA, ST_GeomFromText('POINT(0 0)') geometry) "
          f"to '{setup_dir}/data/ne0.parquet' (format parquet)")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode != 0
    assert "hex" in r.stderr
