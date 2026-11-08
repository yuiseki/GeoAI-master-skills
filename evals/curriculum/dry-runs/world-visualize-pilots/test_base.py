"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_base.py"""

# Tests for base.py: Kontur hexagons (web mercator polygons) -> table `hex` of population and a lon/lat centroid,
# in pilot.duckdb of the working directory. The script runs with `python -I` in tmp_path on a synthetic
# data/kontur.parquet. The DuckDB spatial extension must already be installed locally.
#
# Web mercator: x = R * lon_rad and y = R * ln(tan(45 + lat/2)) with R = 6378137, so 1 degree of longitude is
# 111,319.49 m and latitude 60 is y = 8,399,737.89 m.

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

SCRIPT = Path(__file__).parent / "base.py"


def square(cx, cy, half):
    return (f"POLYGON(({cx - half} {cy - half}, {cx + half} {cy - half}, {cx + half} {cy + half}, "
            f"{cx - half} {cy + half}, {cx - half} {cy - half}))")


def write_kontur(d: Path, rows):
    (d / "data").mkdir()
    c = duckdb.connect()
    c.sql("load spatial")
    c.execute("create table k(h3 varchar, population double, wkt varchar)")
    c.executemany("insert into k values (?, ?, ?)", rows)
    c.sql(f"copy (select h3, population, ST_GeomFromText(wkt) geometry from k) to '{d}/data/kontur.parquet' (format parquet)")


def run(d: Path):
    return subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=d, capture_output=True, text=True)


@pytest.fixture
def hex_table(tmp_path):
    write_kontur(tmp_path, [
        ("h_origin", 10.0, square(0, 0, 10_000)),
        ("h_lon1", 20.0, square(111_319.49, 0, 10_000)),
        ("h_lat60", 30.0, square(0, 8_399_737.89, 1_000)),
    ])
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr
    c = duckdb.connect(str(tmp_path / "pilot.duckdb"), read_only=True)
    c.sql("load spatial")
    rows = c.sql("select h3, pop, ST_X(ctr), ST_Y(ctr) from hex order by h3").fetchall()
    return {h: (pop, x, y) for h, pop, x, y in rows}, r.stdout


def test_one_row_per_hexagon_with_its_population(hex_table):
    rows, _ = hex_table
    assert {h: v[0] for h, v in rows.items()} == {"h_origin": 10.0, "h_lon1": 20.0, "h_lat60": 30.0}


def test_centroids_are_in_lon_lat_order(hex_table):
    rows, _ = hex_table
    assert rows["h_origin"][1:] == pytest.approx((0, 0), abs=1e-9)
    assert rows["h_lon1"][1:] == pytest.approx((1.0, 0), abs=1e-6)
    assert rows["h_lat60"][1:] == pytest.approx((0, 60.0), abs=1e-3)


def test_the_summary_line_counts_and_sums_population(hex_table):
    _, out = hex_table
    # count, sum, min, median
    assert "[(3, 60.0, 10.0, 20.0)]" in out


def test_a_missing_input_fails(tmp_path):
    r = run(tmp_path)
    assert r.returncode != 0
    assert "kontur.parquet" in r.stderr
