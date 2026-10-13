"""uvx --from 'duckdb>=1.5.5' --with pytest pytest test_assign_points.py"""

import math

import duckdb
import pytest

from assign_points import assign


@pytest.fixture
def files(tmp_path):
    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    polygons = tmp_path / "polygons.parquet"
    points = tmp_path / "points.parquet"
    # Two 1-degree squares at 60N sharing the edge x = 1. Away from the equator a degree of
    # longitude is shorter than a degree of latitude, so swapped axes give a wrong distance.
    con.sql(f"""
        copy (select * from (values
            ('A', ST_GeomFromText('POLYGON((0 60, 1 60, 1 61, 0 61, 0 60))')),
            ('B', ST_GeomFromText('POLYGON((1 60, 2 60, 2 61, 1 61, 1 60))'))
        ) t(key, geometry)) to '{polygons}' (format parquet)
    """)
    # Point ids name the expected outcome. Points carry a different CRS name than the polygons,
    # as OurAirports and UCDP GED do against Natural Earth.
    con.sql(f"""
        copy (select id, ST_SetCRS(ST_Point(x, y), 'OGC:CRS84') as geometry from (values
            ('in_a', 0.5, 60.5),
            ('in_b', 1.5, 60.5),
            ('on_edge', 1.0, 60.5),
            ('near_a', -0.01, 60.5),
            ('far', -1.0, 60.5)
        ) t(id, x, y)) to '{points}' (format parquet)
    """)
    return points, polygons, tmp_path / "out.parquet"


def test_every_point_is_accounted_for(files, capsys):
    points, polygons, out = files
    assign(str(points), "id", str(polygons), "key", 5.0, str(out))
    rows = {r[0]: r[1:] for r in duckdb.sql(f"select * from '{out}'").fetchall()}

    assert rows["in_a"][:2] == ("A", "contained")
    assert rows["in_b"][:2] == ("B", "contained")
    assert rows["on_edge"][1] == "contained_multiple"
    assert rows["near_a"][:2] == ("A", "nearest")
    assert rows["far"] == (None, "unassigned", None)
    assert len(rows) == 5

    printed = capsys.readouterr().out
    assert "contained: 2" in printed
    assert "contained_multiple: 1" in printed
    assert "nearest: 1" in printed
    assert "unassigned: 1" in printed


def test_nearest_distance_is_in_kilometres(files):
    points, polygons, out = files
    assign(str(points), "id", str(polygons), "key", 5.0, str(out))
    km = duckdb.sql(f"select km from '{out}' where id = 'near_a'").fetchone()[0]
    # 0.01 degree of longitude at 60.5N, on a sphere of radius 6,371 km: about 0.55 km.
    expected = 2 * math.pi * 6371.0 * 0.01 / 360 * math.cos(math.radians(60.5))
    assert km == pytest.approx(expected, rel=0.01)


def test_duplicate_point_ids_stop_the_run(files, tmp_path):
    _, polygons, _ = files
    dup = tmp_path / "dup.parquet"
    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    con.sql(f"""
        copy (select 'p' as id, ST_Point(0.5, 60.5) as geometry
              union all select 'p', ST_Point(1.5, 60.5)) to '{dup}' (format parquet)
    """)
    with pytest.raises(SystemExit):
        assign(str(dup), "id", str(polygons), "key", 5.0, None)
