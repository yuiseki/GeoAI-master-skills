"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_pilot_refugee_dist.py"""

# Tests for pilot_refugee_dist.py: refugee-weighted distance between origin and asylum country, and the share
# hosted next door, by year. Runs with `python -I` in tmp_path on synthetic data/unhcr.parquet and a pilot.duckdb
# holding the tables `ne` and `nb` that pilot_refugee.py leaves. The DuckDB spatial extension must already be
# installed locally.
#
# Countries are 2 x 2 degree squares centred on the equator meridian: AAA at (0, 0), BBB at (0, 10), CCC at
# (0, 20). Their point on surface is the centre, so AAA-BBB is 10 degrees of arc = 1,111.95 km and AAA-CCC
# 2,223.9 km. Only AAA and BBB are neighbours.

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "pilot_refugee_dist.py"
KM10 = 2 * 3.141592653589793 * 6371.0088 / 36   # 10 degrees of a great circle

UNHCR = [  # Year, origin, asylum, refugees
    (2020, "AAA", "BBB", 100),
    (2020, "AAA", "CCC", 300),
    (2025, "BBB", "AAA", 50),
    (1985, "AAA", "CCC", 7777),   # before 1990: dropped
]


def setup(tmp_path, unhcr):
    d = tmp_path / "data"
    d.mkdir()
    c = duckdb.connect(str(tmp_path / "pilot.duckdb"))
    c.sql("load spatial")
    c.sql("""create table ne as select iso3, ST_SetCRS(ST_GeomFromText(wkt), 'OGC:CRS84') g from (values
        ('AAA', 'POLYGON((-1 -1, 1 -1, 1 1, -1 1, -1 -1))'),
        ('BBB', 'POLYGON((-1 9, 1 9, 1 11, -1 11, -1 9))'),
        ('CCC', 'POLYGON((-1 19, 1 19, 1 21, -1 21, -1 19))')) t(iso3, wkt)""")
    c.sql("create table nb as select * from (values ('AAA', 'BBB'), ('BBB', 'AAA')) t(x, y)")
    c.execute("create table u(y int, o varchar, a varchar, r bigint)")
    c.executemany("insert into u values (?, ?, ?, ?)", unhcr)
    c.sql(f"""copy (select y "Year", o "Country of origin (ISO)", a "Country of asylum (ISO)",
              r "Refugees under UNHCR's mandate" from u) to '{d}/unhcr.parquet' (format parquet)""")
    c.sql("drop table u")
    c.close()
    r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return duckdb.connect(str(tmp_path / "pilot.duckdb"), read_only=True), r.stdout


def by_year(out):
    rows = eval(out.splitlines()[1], {"Decimal": Decimal})
    return {row[0]: row[1:] for row in rows}


def test_pair_distances_between_points_on_surface(tmp_path):
    c, _ = setup(tmp_path, UNHCR)
    got = {(o, a): (d, adj) for o, a, d, adj in c.sql("select o, a, cdist, adj from pd").fetchall()}
    assert got.keys() == {("AAA", "BBB"), ("AAA", "CCC"), ("BBB", "AAA")}
    assert got[("AAA", "BBB")][0] == pytest.approx(KM10, abs=1)
    assert got[("AAA", "CCC")][0] == pytest.approx(2 * KM10, abs=1)
    assert [got[p][1] for p in [("AAA", "BBB"), ("AAA", "CCC"), ("BBB", "AAA")]] == [True, False, True]


def test_yearly_rows_weight_distance_by_refugees(tmp_path):
    _, out = setup(tmp_path, UNHCR)
    years = by_year(out)
    assert sorted(years) == [2020, 2025]   # 1985 is before 1990; other listed years have no rows
    r_m, adj_share, _, mean_km, unmatched = years[2020]
    # with every pair on the map the unmatched sum is over no rows, so it prints None rather than 0
    assert (r_m, adj_share, unmatched) == (0.0, 0.25, None)
    # (100 * 1,112 + 300 * 2,224) / 400
    assert mean_km == pytest.approx(round((100 * KM10 + 300 * 2 * KM10) / 400), abs=1)
    assert years[2025][1] == 1.0 and years[2025][3] == pytest.approx(round(KM10), abs=1)


def test_unmatched_refugees_do_not_pull_the_weighted_distance_down(tmp_path):
    # 2025: 50 from BBB to AAA (1,112 km), and 50 from XXX, which is not on the map
    _, out = setup(tmp_path, UNHCR + [(2025, "XXX", "AAA", 50)])
    r_m, adj_share, _, mean_km, unmatched = by_year(out)[2025]
    assert unmatched == 0.5
    assert mean_km == pytest.approx(round(KM10), abs=1)
