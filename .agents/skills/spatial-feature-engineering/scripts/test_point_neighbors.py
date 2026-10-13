"""uvx --from 'duckdb>=1.5.5' --with pytest pytest test_point_neighbors.py"""

import math

import duckdb
import pytest

from point_neighbors import neighbors


def haversine_km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def write_points(path, rows):
    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    values = ", ".join(f"('{i}', {x}, {y})" for i, x, y in rows)
    con.sql(f"""
        copy (select id, ST_SetCRS(ST_Point(x, y), 'OGC:CRS84') as geometry
              from (values {values}) t(id, x, y)) to '{path}' (format parquet)
    """)


QUERY = [
    ("q60", 0.0, 60.0),     # at 60N a degree of longitude is half a degree of latitude
    ("qam", 179.99, 0.0),   # beside the antimeridian
    ("qalone", -100.0, -60.0),
]
REFERENCE = [
    ("east", 0.1, 60.0),     # about 5.6 km from q60
    ("north", 0.0, 60.1),    # about 11.1 km
    ("far_east", 1.0, 60.0), # about 55.6 km
    ("across", -179.99, 0.0),  # about 2.2 km from qam, on the other side of 180
]


@pytest.fixture
def result(tmp_path):
    q, r, out = tmp_path / "q.parquet", tmp_path / "r.parquet", tmp_path / "out.parquet"
    write_points(q, QUERY)
    write_points(r, REFERENCE)
    neighbors(str(q), "id", str(r), "id", [10, 50], False, None, None, str(out))
    return {row[0]: row[1:] for row in duckdb.sql(f"select * from '{out}'").fetchall()}


def test_counts_within_radii(result):
    assert result["q60"][:2] == (1, 2)   # east within 10 km; east and north within 50 km
    assert result["qam"][:2] == (1, 1)
    assert result["qalone"][:2] == (0, 0)


def test_nearest_is_great_circle_km_at_high_latitude(result):
    assert result["q60"][2] == pytest.approx(haversine_km(0, 60, 0.1, 60), rel=1e-6)


def test_nearest_crosses_the_antimeridian(result):
    assert result["qam"][2] == pytest.approx(haversine_km(179.99, 0, -179.99, 0), rel=1e-6)


def test_nothing_within_the_largest_radius_is_null_not_dropped(result):
    assert set(result) == {"q60", "qam", "qalone"}
    assert result["qalone"][2] is None


def test_exclude_self(tmp_path):
    p, out = tmp_path / "p.parquet", tmp_path / "out.parquet"
    write_points(p, [("a", 0.0, 60.0), ("b", 0.1, 60.0)])
    neighbors(str(p), "id", str(p), "id", [10], True, None, None, str(out))
    rows = dict(duckdb.sql(f"select id, n_within_10km from '{out}'").fetchall())
    assert rows == {"a": 1, "b": 1}
    neighbors(str(p), "id", str(p), "id", [10], False, None, None, str(out))
    rows = dict(duckdb.sql(f"select id, n_within_10km from '{out}'").fetchall())
    assert rows == {"a": 2, "b": 2}
