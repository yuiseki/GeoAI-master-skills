"""uvx --from pytest --with 'duckdb>=1.5.5' pytest test_profile_layer.py"""

import duckdb

from profile_layer import profile


def write(path, sql):
    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    con.sql(f"copy ({sql}) to '{path}' (format parquet)")
    return str(path)


def test_counts_rows_nulls_types_extent_and_invalid(tmp_path, capsys):
    p = write(tmp_path / "a.parquet", """
        select * from (values
          ('a', ST_Point(1, -3)),
          (NULL, ST_Point(10, 5)),
          ('c', ST_GeomFromText('POLYGON((2 2, 4 4, 4 2, 2 4, 2 2))')),
          ('d', NULL::GEOMETRY)) t(name, geometry)""")
    profile(p)
    out = capsys.readouterr().out
    assert "rows: 4" in out
    assert "name\tVARCHAR\tnull=1" in out
    assert "null=1" in out.split("geometry\t")[1].splitlines()[0]
    assert "geometry: POINT 2" in out and "geometry: POLYGON 1" in out
    assert "extent: 1.0 -3.0 10.0 5.0" in out         # x and y ranges differ, so a swapped bound shows
    assert "invalid: 1" in out                      # the bow tie crosses itself


def test_a_table_without_geometry_says_so(tmp_path, capsys):
    profile(write(tmp_path / "b.parquet", "select 1 as x"))
    assert "geometry: no column" in capsys.readouterr().out


def test_a_geometry_column_that_is_all_null_says_so(tmp_path, capsys):
    profile(write(tmp_path / "c.parquet", "select 1 as x, NULL::GEOMETRY as geometry"))
    assert "every value NULL" in capsys.readouterr().out
