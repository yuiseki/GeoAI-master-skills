"""uvx --from 'duckdb>=1.5.5' --with pytest pytest test_compare_positions.py

Distances are worked out by hand on a sphere of radius 6,371 km: 0.001 degree of longitude at the equator
and 0.002 degree at 60N are both 111.19 m (cos 60 = 0.5).
"""

import math

import duckdb
import pytest

from compare_positions import compare

M_PER_DEG = 6371000 * math.pi / 180


def write(path, rows):
    vals = ", ".join(f"('{k}', {lon}, {lat})" for k, lon, lat in rows)
    duckdb.sql(f"copy (select * from (values {vals}) t(name, lon, lat)) to '{path}' (format parquet)")
    return str(path)


def test_matches_by_key_measures_metres_and_lists_what_did_not_match(tmp_path):
    a = write(tmp_path / "a.parquet", [("A", 0, 0), ("B", 0, 60), ("C", 10, 0)])
    b = write(tmp_path / "b.parquet", [("A", 0.001, 0), ("B", 0.002, 60), ("D", 5, 5)])
    r = compare(a, b, "name", radii=[50, 200])
    assert (r["left_rows"], r["right_rows"], r["matched"]) == (3, 3, 2)
    assert r["unmatched_left"] == ["C"] and r["unmatched_right"] == ["D"]
    d = sorted(r["distances"])
    assert d[0] == pytest.approx(0.001 * M_PER_DEG, rel=1e-3)        # 111.19 m
    assert d[1] == pytest.approx(0.002 * M_PER_DEG * 0.5, rel=1e-3)  # also 111.19 m; 222 m if degrees were taken flat
    assert r["rmse_m"] == pytest.approx(111.19, abs=0.2)
    assert r["share_over"] == {50: 1.0, 200: 0.0}


def test_several_candidates_take_the_nearest_and_are_counted(tmp_path):
    a = write(tmp_path / "a.parquet", [("A", 0, 0)])
    b = write(tmp_path / "b.parquet", [("A", 0.01, 0), ("A", 0.001, 0)])
    r = compare(a, b, "name")
    assert r["distances"][0] == pytest.approx(0.001 * M_PER_DEG, rel=1e-3)
    assert r["left_with_several_candidates"] == 1


def test_a_missing_coordinate_is_counted_not_matched(tmp_path):
    a = write(tmp_path / "a.parquet", [("A", 0, 0), ("B", "NULL", "NULL")])
    b = write(tmp_path / "b.parquet", [("A", 0.001, 0), ("B", 1, 1)])
    r = compare(a, b, "name")
    assert r["missing_coordinates_left"] == 1 and r["matched"] == 1
