"""uvx --from 'duckdb>=1.5.5' --with pytest pytest test_poi_extract.py"""

# Tests for poi_extract.py on a tiny table with the Overture places columns: every row is either kept or dropped
# for one counted reason, and the category matches the basic category or any level of the taxonomy.

import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from poi_extract import extract

ROWS = [
    # id, lon, lat, basic_category, hierarchy, brand, status, confidence, dataset
    ("a", 0.10, 51.50, "coffee_shop", ["food_and_drink", "non_alcoholic_beverage_venue", "coffee_shop"], "Costa", "open", 0.9, "meta"),
    ("b", 0.11, 51.50, "cafe", ["food_and_drink", "cafe"], None, None, 0.6, "Microsoft"),
    ("c", 0.12, 51.50, "coffee_roastery", ["food_and_drink", "non_alcoholic_beverage_venue", "coffee_shop", "coffee_roastery"], None, "open", 0.8, "Foursquare"),
    ("d", 0.13, 51.50, "coffee_shop", ["food_and_drink", "non_alcoholic_beverage_venue", "coffee_shop"], "Starbucks", "permanently_closed", 0.9, "meta"),
    ("e", 0.14, 51.50, "coffee_shop", ["food_and_drink", "non_alcoholic_beverage_venue", "coffee_shop"], None, "open", 0.2, "meta"),
    ("f", 0.15, 51.50, "bakery", ["food_and_drink", "bakery"], None, "open", 0.9, "meta"),
    ("h", 0.16, 51.50, None, None, None, None, 0.9, "meta"),            # no category at all
    ("g", 5.00, 51.50, "coffee_shop", ["food_and_drink", "non_alcoholic_beverage_venue", "coffee_shop"], None, "open", 0.9, "meta"),
]


@pytest.fixture
def places(tmp_path):
    p = tmp_path / "places.parquet"
    c = duckdb.connect()
    c.sql("install spatial; load spatial")
    c.sql("""create table t (id varchar, lon double, lat double, basic_category varchar, h varchar[], brand_name varchar,
             operating_status varchar, confidence double, ds varchar)""")
    c.executemany("insert into t values (?, ?, ?, ?, ?, ?, ?, ?, ?)", ROWS)
    c.sql(f"""copy (select id, st_point(lon, lat) as geometry,
                 {{'xmin': lon, 'xmax': lon, 'ymin': lat, 'ymax': lat}} as bbox,
                 {{'primary': 'name ' || id}} as names, basic_category,
                 {{'primary': basic_category, 'hierarchy': h}} as taxonomy,
                 case when brand_name is null then null else {{'names': {{'primary': brand_name}}}} end as brand,
                 operating_status, confidence,
                 [{{'dataset': ds, 'license': 'CDLA-Permissive-2.0'}}] as sources
              from t) to '{p}' (format parquet)""")
    return p


BBOX = (0.0, 51.0, 1.0, 52.0)


def test_coffee_by_category_or_taxonomy(places):
    rows, audit = extract(str(places), BBOX, ["coffee_shop"], exclude_status=["permanently_closed"], min_confidence=0.5)
    assert sorted(r["id"] for r in rows) == ["a", "c"]          # c is a coffee_shop by its taxonomy
    assert audit == {"in_bbox": 7, "other_category": 3, "excluded_status": 1, "low_confidence": 1, "kept": 2}


def test_unknown_status_is_kept_and_named_unknown(places):
    rows, audit = extract(str(places), BBOX, ["cafe"], exclude_status=["permanently_closed"], min_confidence=0)
    assert [(r["id"], r["operating_status"]) for r in rows] == [("b", "unknown")]


def test_fields_brand_hierarchy_and_sources(places):
    rows, _ = extract(str(places), BBOX, ["coffee_shop"], exclude_status=[], min_confidence=0)
    a = next(r for r in rows if r["id"] == "a")
    assert a["brand"] == "Costa" and a["name"] == "name a" and a["sources"] == "meta"
    assert a["hierarchy"] == "food_and_drink>non_alcoholic_beverage_venue>coffee_shop"
    assert (a["lon"], a["lat"]) == pytest.approx((0.10, 51.50))
    assert {r["id"] for r in rows} == {"a", "c", "d", "e"}


def test_no_category_keeps_every_category(places):
    _, audit = extract(str(places), BBOX, [], exclude_status=[], min_confidence=0)
    assert audit["kept"] == 7 and audit["other_category"] == 0


def test_cli_writes_parquet_and_audit(places, tmp_path):
    out = tmp_path / "out.parquet"
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("poi_extract.py")), str(places), str(out),
                        "--bbox", "0", "51", "1", "52", "--category", "coffee_shop", "--min-confidence", "0.5",
                        "--exclude-status", "permanently_closed"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(Path(str(out) + ".audit.json").read_text())["counts"]["kept"] == 2
    assert duckdb.connect().execute(f"select count(*) from '{out}'").fetchall()[0][0] == 2
