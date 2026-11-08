"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with tzdata --with pytest pytest -q test_pilot_tz.py"""

# Tests for pilot_tz.py: legal clock minus mean solar time (lon / 15 hours) at each populated cell, in January
# and July 2025. Runs with `python -I` in tmp_path on a synthetic pilot.duckdb (table hexcty) and data/tz.parquet.
# The DuckDB spatial extension must already be installed locally; zone rules come from the tzdata package.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_tz.py"

ZONES = [  # tzid, wkt
    ("Asia/Tokyo", "POLYGON((130 30, 150 30, 150 45, 130 45, 130 30))"),
    ("Europe/London", "POLYGON((-10 49, 2 49, 2 60, -10 60, -10 49))"),
    ("Asia/Shanghai", "POLYGON((73 20, 125 20, 125 50, 73 50, 73 20))"),
]
CELLS = [  # h3, pop, a3, lon, lat
    ("c_tokyo_135", 100.0, "JPN", 135.0, 35.0),   # +9 - 135/15 = 0
    ("c_tokyo_145", 300.0, "JPN", 145.0, 40.0),   # +9 - 145/15 = -0.6667
    ("c_london_0", 200.0, "GBR", 0.0, 51.5),      # Jan 0 - 0 = 0, Jul +1 - 0 = 1
    ("c_west_china", 50.0, "CHN", 87.0, 43.0),    # +8 - 87/15 = 2.2
    ("c_ocean", 10.0, "XXX", -40.0, 0.0),         # in no zone
]


@pytest.fixture
def db(tmp_path):
    (tmp_path / "data").mkdir()
    c = duckdb.connect(str(tmp_path / "pilot.duckdb"))
    c.sql("load spatial")
    c.execute("create table z(tzid varchar, wkt varchar)")
    c.executemany("insert into z values (?, ?)", ZONES)
    c.sql(f"copy (select tzid, ST_GeomFromText(wkt) geometry from z) to '{tmp_path}/data/tz.parquet' (format parquet)")
    c.sql("drop table z")
    c.execute("create table h(h3 varchar, pop double, a3 varchar, lon double, lat double)")
    c.executemany("insert into h values (?, ?, ?, ?, ?)", CELLS)
    c.sql("create table hexcty as select h3, pop, ST_Point(lon, lat) ctr, a3, false nearest from h")
    c.sql("drop table h")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    con = duckdb.connect(str(tmp_path / "pilot.duckdb"), read_only=True)
    return con, r.stdout


def test_zone_offsets_in_january_and_july(db):
    c, _ = db
    got = {tz: (jan, jul) for tz, jan, jul in c.sql("select * from tzoff").fetchall()}
    assert got == {"Asia/Tokyo": (9.0, 9.0), "Europe/London": (0.0, 1.0), "Asia/Shanghai": (8.0, 8.0)}


def test_deviation_is_clock_minus_lon_over_15(db):
    c, _ = db
    got = {h: (j, u) for h, j, u in c.sql("select h3, dev_jan, dev_jul from dev").fetchall()}
    assert got.keys() == {"c_tokyo_135", "c_tokyo_145", "c_london_0", "c_west_china"}
    assert got["c_tokyo_135"] == pytest.approx((0, 0))
    assert got["c_tokyo_145"] == pytest.approx((-2 / 3, -2 / 3))
    assert got["c_london_0"] == pytest.approx((0, 1))
    assert got["c_west_china"] == pytest.approx((2.2, 2.2))


def test_cells_outside_every_zone_are_counted_not_dropped_silently(db):
    _, out = db
    # count, distinct cells, cells with no zone, their population in millions rounded
    assert "[(5, 5, 1, 0.0)]" in out


def test_the_population_weighted_mean_absolute_deviation(db):
    _, out = db
    # Jan: (300 * 2/3 + 50 * 2.2) / 650 = 0.48; Jul adds London: (200 + 110 + 200) / 650 = 0.78
    line = next(l for l in out.splitlines() if l.startswith("[(0.48"))
    assert line.startswith("[(0.48, 0.78,")
