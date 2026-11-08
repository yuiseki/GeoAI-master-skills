"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_gtfs.py"""

# Tests for pilot_gtfs.py: population whose cell centroid lies inside the bounding box of an active GTFS feed
# (all boxes, and boxes of 25 square degrees or less), by country. Runs with `python -I` in tmp_path on synthetic
# data/feeds_v2.csv, data/ne0.parquet and data/wdi.parquet and a pilot.duckdb holding table hexcty. The DuckDB
# spatial and h3 extensions must already be installed locally.
#
# Cell centroids: A at (lon 10, lat 10) in AAA, N at (lon 10.3, lat 10) in BBB, F at (lon -60, lat -30) in FFF.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_gtfs.py"

HEADER = ("id,data_type,location.country_code,is_official,status,urls.authentication_type,"
          "location.bounding_box.minimum_latitude,location.bounding_box.maximum_latitude,"
          "location.bounding_box.minimum_longitude,location.bounding_box.maximum_longitude")
FEEDS = [
    "f1,gtfs,AA,True,active,0,9.5,10.5,9.5,10.1",        # 1 x 0.6 = 0.6 deg2, covers A only
    "f2,gtfs,FF,False,,0,-40,-20,-70,-50",               # 20 x 20 = 400 deg2, covers F; too big for the cap
    "f3,gtfs,BB,True,deprecated,0,9,11,10.2,10.4",       # covers N but deprecated
    "f4,gtfs_rt,BB,True,active,0,9,11,10.2,10.4",        # realtime, not a schedule
    "f5,gtfs,BB,True,active,0,11,9,10.2,10.4",           # south above north: a broken box
    "f6,gtfs,BB,True,active,0,,,,",                      # no box
]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("gtfs")
    (d / "data").mkdir()
    (d / "data" / "feeds_v2.csv").write_text("\n".join([HEADER, *FEEDS]) + "\n")
    c = duckdb.connect(str(d / "pilot.duckdb"))
    c.sql("load spatial")
    c.sql("""create table hexcty as select * from (values
        ('A', 1e6, ST_Point(10, 10), 'AAA'), ('N', 2e6, ST_Point(10.3, 10), 'BBB'),
        ('F', 3e6, ST_Point(-60, -30), 'FFF')) t(h3, pop, ctr, a3)""")
    c.sql(f"""copy (select * from (values ('AA', 'AAA'), ('BB', 'BBB'), ('FF', 'FFF'), ('-99', '-99'))
              t(ISO_A2_EH, ISO_A3_EH)) to '{d}/data/ne0.parquet' (format parquet)""")
    c.sql(f"""copy (select * from (values ('AAA', 'NY.GDP.PCAP.CD', 2023, 5000.0), ('FFF', 'NY.GDP.PCAP.CD', 2023, 800.0))
              t(country_code, indicator_code, year, value)) to '{d}/data/wdi.parquet' (format parquet)""")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(d / "pilot.duckdb"), read_only=True), r.stdout


def test_only_active_schedule_feeds_with_a_proper_box_are_kept(run):
    c, _ = run
    assert dict(c.sql("select id, deg2 from g").fetchall()) == pytest.approx({"f1": 0.6, "f2": 400.0})


def test_cells_inside_a_box(run):
    c, _ = run
    assert sorted(r[0] for r in c.sql("select h3 from cov_all").fetchall()) == ["A", "F"]
    assert [r[0] for r in c.sql("select h3 from cov_cap25").fetchall()] == ["A"]


def test_population_in_boxes_by_country(run):
    c, out = run
    got = {a3: (pop, i, j) for a3, pop, i, j in c.sql("select a3, pop, in_all, in_cap from cty").fetchall()}
    assert got == {"AAA": (1e6, 1e6, 1e6), "BBB": (2e6, None, None), "FFF": (3e6, 3e6, None)}
    # world share: all boxes 4M / 6M, capped boxes 1M / 6M
    assert "world share in bbox [(0.667, 0.167)]" in out


def test_feeds_per_country_through_iso2(run):
    c, _ = run
    assert sorted(c.sql("select a3, n, n_off from nfeeds").fetchall()) == [("AAA", 1, 1), ("FFF", 1, 0)]


@pytest.mark.xfail(strict=True, reason="BUG: the 'corr share vs ln gdppc' line uses in_cap/pop, which is NULL, not 0, "
                                       "for a country with no covered cell, so uncovered countries drop out of the "
                                       "correlation (the fit table below it uses coalesce and keeps them)")
def test_uncovered_countries_count_as_a_share_of_zero_in_the_correlation(tmp_path):
    # shares by ln(gdppc): AAA (10, 1.0), CCC (9, 0.5), BBB (9.5, 0). corr = 0.25 / sqrt(0.5 * 0.5) = 0.5;
    # with BBB dropped, two points give 1.0
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "feeds_v2.csv").write_text("\n".join([
        HEADER, "f1,gtfs,AA,True,active,0,9.5,10.5,9.5,10.5", "f2,gtfs,CC,True,active,0,29.5,30.5,29.5,30.5"]) + "\n")
    c = duckdb.connect(str(tmp_path / "pilot.duckdb"))
    c.sql("load spatial")
    c.sql("""create table hexcty as select * from (values
        ('A', 6e6, ST_Point(10, 10), 'AAA'), ('B', 6e6, ST_Point(20, 20), 'BBB'),
        ('C1', 3e6, ST_Point(30, 30), 'CCC'), ('C2', 3e6, ST_Point(40, 40), 'CCC')) t(h3, pop, ctr, a3)""")
    c.sql(f"""copy (select * from (values ('AA', 'AAA'), ('BB', 'BBB'), ('CC', 'CCC')) t(ISO_A2_EH, ISO_A3_EH))
              to '{tmp_path}/data/ne0.parquet' (format parquet)""")
    c.sql(f"""copy (select country_code, 'NY.GDP.PCAP.CD' indicator_code, 2023 "year", exp(l) "value" from (values
              ('AAA', 10.0), ('BBB', 9.5), ('CCC', 9.0)) t(country_code, l)) to '{tmp_path}/data/wdi.parquet' (format parquet)""")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    line = next(l for l in r.stdout.splitlines() if l.startswith("corr share vs ln gdppc "))
    n, corr_share, _ = eval(line[len("corr share vs ln gdppc "):])[0]
    assert n == 3
    assert corr_share == pytest.approx(0.5)
