"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_cyclone.py"""

# Tests for pilot_cyclone.py: population in H3 r4 cells within k rings of a 1980-2025 IBTrACS point at 64 kt or
# more, by wind source (USA, WMO). Runs with `python -I` in tmp_path on a synthetic data/ibtracs.parquet and a
# pilot.duckdb holding table hexcty. The DuckDB h3 extension must already be installed locally.
#
# Cells: A holds (lat 10, lon 10); N is one of A's neighbours; F holds (lat -30, lon -60).
# Populations: A 1M in AAA, N 2M in BBB, F 3M in FFF. Wind columns are text, as in the IBTrACS CSV, with blanks.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_cyclone.py"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("cyclone")
    (d / "data").mkdir()
    c = duckdb.connect(str(d / "pilot.duckdb"))
    c.sql("load h3")
    a = c.sql("select h3_latlng_to_cell_string(10, 10, 4)").fetchall()[0][0]
    n = sorted(set(c.sql(f"select h3_grid_disk('{a}', 1)").fetchall()[0][0]) - {a})[0]
    f = c.sql("select h3_latlng_to_cell_string(-30, -60, 4)").fetchall()[0][0]
    c.execute("create table hexcty(h3 varchar, pop double, a3 varchar)")
    c.executemany("insert into hexcty values (?, ?, ?)", [(a, 1e6, "AAA"), (n, 2e6, "BBB"), (f, 3e6, "FFF")])
    c.sql(f"""copy (select SID, ISO_TIME::timestamp ISO_TIME, USA_WIND, WMO_WIND, USA_R64_NE, BASIN, WMO_AGENCY,
                           LAT, LON from (values
        ('S1', '2000-08-01 00:00:00', '70', '60', '', 'WP', 'tokyo', 10.0, 10.0),
        ('S1', '2000-08-01 06:00:00', '75', '62', '', 'WP', 'tokyo', 10.0, 10.0),
        ('S2', '2010-02-01 00:00:00', '50', '65', '', 'SI', 'reunion', -30.0, -60.0),
        ('S3', '2020-09-01 00:00:00', '80', ' ', '', 'WP', '', 10.0, 10.0),
        ('S0', '1975-09-01 00:00:00', '100', '100', '', 'NA', 'hurdat', -30.0, -60.0))
        t(SID, ISO_TIME, USA_WIND, WMO_WIND, USA_R64_NE, BASIN, WMO_AGENCY, LAT, LON))
        to '{d}/data/ibtracs.parquet' (format parquet)""")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(d / "pilot.duckdb"), read_only=True), r.stdout


def exposure(c, name):
    return {a3: (p, s) for a3, p, s in c.sql(f"select a3, pop_m, popstorms_m from {name}").fetchall()}


def test_points_before_1980_are_dropped_and_blank_winds_are_null(run):
    c, _ = run
    assert c.sql("select count(*), count(usa), count(wmo) from tp").fetchall() == [(4, 4, 3)]


def test_usa_wind_exposure_counts_distinct_storms_per_cell(run):
    c, _ = run
    # S1 (two points) and S3 reach A and its ring: two storms, not three points
    assert exposure(c, "e_usa_1") == {"AAA": (1.0, 2.0), "BBB": (2.0, 4.0)}
    assert exposure(c, "e_usa_2") == {"AAA": (1.0, 2.0), "BBB": (2.0, 4.0)}


def test_wmo_wind_gives_a_different_answer(run):
    c, out = run
    # only S2 is 64 kt by WMO
    assert exposure(c, "e_wmo_1") == {"FFF": (3.0, 3.0)}
    assert "overlap usa1/wmo1 0 usa1/usa2 2" in out
