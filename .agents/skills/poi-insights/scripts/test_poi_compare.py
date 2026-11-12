"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with h3 --with pytest pytest test_poi_compare.py"""

# Tests for poi_compare.py: two square regions with known points, brands and people.

import json
import math

import duckdb
import h3
import pytest

from poi_compare import compare, hhi, local_metres


def write_regions(path):
    c = duckdb.connect()
    c.execute("install spatial; load spatial")
    c.execute(f"""copy (select * from (values
        ('A', 'west', st_geomfromtext('POLYGON((0 0, 0.01 0, 0.01 0.01, 0 0.01, 0 0))')),
        ('B', 'east', st_geomfromtext('POLYGON((0.02 0, 0.03 0, 0.03 0.01, 0.02 0.01, 0.02 0))'))
        ) t(region_id, region_name, geometry)) to '{path}' (format parquet)""")


def write_points(path, rows):
    c = duckdb.connect()
    c.execute("create table p (id varchar, lon double, lat double, brand varchar, operating_status varchar)")
    c.executemany("insert into p values (?, ?, ?, ?, ?)", rows)
    c.execute(f"copy p to '{path}' (format parquet)")


ROWS = [
    ("1", 0.002, 0.005, "X", "open"), ("2", 0.004, 0.005, "X", "open"), ("3", 0.006, 0.005, "Y", "unknown"),
    ("4", 0.008, 0.005, None, "open"),
    ("5", 0.025, 0.005, "X", "open"),
    ("6", 0.5, 0.5, "X", "open"),                     # in no region
]


def test_hhi_counts_each_unbranded_place_as_its_own_firm():
    assert hhi({"X": 2, "Y": 1}, unbranded=1) == pytest.approx((0.5 ** 2) + (0.25 ** 2) + (0.25 ** 2))
    assert hhi({"X": 5}, unbranded=0) == pytest.approx(1.0)


def test_local_metres_is_right_at_the_equator_and_at_60_degrees():
    x, y = local_metres([0.0, 0.001], [0.0, 0.0], 0.0)
    assert x[1] - x[0] == pytest.approx(111.32, rel=0.01)
    x, y = local_metres([0.0, 0.001], [60.0, 60.0], 60.0)
    assert x[1] - x[0] == pytest.approx(111.32 * 0.5, rel=0.01)


def test_counts_density_brands_and_competition(tmp_path):
    write_regions(tmp_path / "r.parquet")
    write_points(tmp_path / "p.parquet", ROWS)
    out = compare(str(tmp_path / "p.parquet"), str(tmp_path / "r.parquet"))
    a, b = out["regions"]["A"], out["regions"]["B"]
    assert (a["poi"], b["poi"]) == (4, 1) and out["audit"] == {"points": 6, "in_a_region": 5, "in_no_region": 1}
    km2 = (0.01 * 111.32) * (0.01 * 111.32 * math.cos(math.radians(0.005)))
    assert a["area_km2"] == pytest.approx(km2, rel=0.01)
    assert a["per_km2"] == pytest.approx(4 / km2, rel=0.01)
    assert a["top_brand"] == "X" and a["top_brand_share"] == pytest.approx(0.5)
    assert a["branded_share"] == pytest.approx(0.75) and a["unknown_status_share"] == pytest.approx(0.25)
    assert a["hhi"] == pytest.approx(0.5 ** 2 + 0.25 ** 2 + 0.25 ** 2)
    # Nearest place of another brand (or unbranded) for X at 0.004 is Y at 0.006: about 222 m.
    assert a["median_m_to_other_brand"] == pytest.approx(222.6, rel=0.02)


def test_people_per_place_and_coverage_from_population_cells(tmp_path):
    write_regions(tmp_path / "r.parquet")
    write_points(tmp_path / "p.parquet", ROWS)
    near = h3.latlng_to_cell(0.005, 0.0045, 9)        # next to points 2 and 3
    far = h3.latlng_to_cell(0.005, 0.029, 9)          # about 450 m from point 5
    c = duckdb.connect()
    c.execute("create table pop (h3 varchar, population double)")
    c.executemany("insert into pop values (?, ?)", [(near, 1000.0), (far, 3000.0)])
    c.execute(f"copy pop to '{tmp_path / 'pop.parquet'}' (format parquet)")
    out = compare(str(tmp_path / "p.parquet"), str(tmp_path / "r.parquet"),
                  population=str(tmp_path / "pop.parquet"), within_m=300)
    a, b = out["regions"]["A"], out["regions"]["B"]
    assert a["population"] == 1000 and b["population"] == 3000
    assert a["poi_per_10k"] == pytest.approx(40.0) and b["poi_per_10k"] == pytest.approx(1 / 0.3)
    assert a["pop_share_within_m"] == pytest.approx(1.0) and b["pop_share_within_m"] == pytest.approx(0.0)
