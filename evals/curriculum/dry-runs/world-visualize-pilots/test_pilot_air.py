"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_air.py"""

# Tests for pilot_air.py: population far (more than k H3 r4 rings) from an open airport with a long paved runway,
# and from any airport with scheduled service. Runs with `python -I` in tmp_path on synthetic
# data/airports.parquet and data/runways.parquet and a pilot.duckdb holding table hexcty. The DuckDB h3 extension
# must already be installed locally.
#
# Cells: A holds (lat 10, lon 10); N is one of A's neighbours; F holds (lat -30, lon -60).
# Populations: A 1M in AAA, N 2M in BBB, F 3M in FFF.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_air.py"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("air")
    (d / "data").mkdir()
    c = duckdb.connect(str(d / "pilot.duckdb"))
    c.sql("load h3")
    a = c.sql("select h3_latlng_to_cell_string(10, 10, 4)").fetchall()[0][0]
    n = sorted(set(c.sql(f"select h3_grid_disk('{a}', 1)").fetchall()[0][0]) - {a})[0]
    f = c.sql("select h3_latlng_to_cell_string(-30, -60, 4)").fetchall()[0][0]
    nlat, nlon = c.sql(f"select h3_cell_to_lat('{n}'), h3_cell_to_lng('{n}')").fetchall()[0]
    c.execute("create table hexcty(h3 varchar, pop double, a3 varchar)")
    c.executemany("insert into hexcty values (?, ?, ?)", [(a, 1e6, "AAA"), (n, 2e6, "BBB"), (f, 3e6, "FFF")])
    c.sql(f"""copy (select * from (values
        ('AP1', 'large_airport', 'yes', 'AA', 10.0, 10.0),
        ('AP2', 'medium_airport', 'no', 'FF', -30.0, -60.0),
        ('AP3', 'heliport', 'yes', 'FF', -30.0, -60.0),
        ('AP4', 'small_airport', 'no', 'BB', {nlat}, {nlon}))
        t(ident, type, scheduled_service, iso_country, latitude_deg, longitude_deg))
        to '{d}/data/airports.parquet' (format parquet)""")
    c.sql(f"""copy (select * from (values
        ('AP1', 7000, 'ASPH', 0),
        ('AP2', 9000, 'CON', 1),       -- closed
        ('AP2', 9000, 'turf', 0),      -- not paved
        ('AP3', 9000, 'ASP', 0),       -- a heliport is not an airport here
        ('AP4', 6500, ' asp ', 0))     -- case and spaces are trimmed
        t(airport_ident, length_ft, surface, closed))
        to '{d}/data/runways.parquet' (format parquet)""")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(d / "pilot.duckdb"), read_only=True), r.stdout, (a, n, f)


def test_longest_open_paved_runway_per_airport(run):
    c, _, (a, n, f) = run
    got = {i: (cell, plen) for i, cell, plen in c.sql("select ident, cell, paved_len from ap").fetchall()}
    assert got == {"AP1": (a, 7000), "AP2": (f, None), "AP4": (n, 6500)}


def test_population_far_from_airports(run):
    _, out, _ = run
    lines = out.splitlines()
    far = {}
    for i, line in enumerate(lines):
        if line.split(" ")[0] in ("sched", "paved6000", "paved8000"):
            far[line.split(" ")[0]] = (lines[i + 1], lines[i + 2])
    # scheduled: AP1 at A covers A and N within 3 rings, so F (3M) is far
    assert far["sched"] == (" k 3 [(3.0,)]", " k 5 [(3.0,)]")
    assert far["paved6000"] == (" k 3 [(3.0,)]", " k 5 [(3.0,)]")
    # no runway reaches 8,000 ft: everyone is far
    assert far["paved8000"] == (" k 3 [(6.0,)]", " k 5 [(6.0,)]")
    assert "sched [(1,)]" in lines and "paved6000 [(2,)]" in lines and "paved8000 [(0,)]" in lines
