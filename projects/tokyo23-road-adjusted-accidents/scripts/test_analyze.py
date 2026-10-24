"""Known-answer tests for task 31; run before the data analysis."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "road_accidents", Path(__file__).with_name("analyze.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_road_classes_include_links_but_exclude_nonmotorized():
    assert MODULE.is_primary_road("residential")
    assert MODULE.is_primary_road("primary_link")
    assert MODULE.is_primary_road("service")
    assert not MODULE.is_primary_road("footway")
    assert not MODULE.is_primary_road("construction")
    assert not MODULE.is_primary_road(None)


def test_road_clipping_conserves_length_across_two_meshes():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("load spatial")
    con.execute("create table lines (id integer, way geometry)")
    con.execute("insert into lines values (1, ST_GeomFromText('LINESTRING(0 0, 2 0)'))")
    con.execute("create table cells (mesh varchar, geometry geometry)")
    con.execute("insert into cells values ('a', ST_GeomFromText('POLYGON((0 -1,1 -1,1 1,0 1,0 -1))')), ('b', ST_GeomFromText('POLYGON((1 -1,2 -1,2 1,1 1,1 -1))'))")
    lengths = MODULE.clip_road_lengths(con, "lines", "cells", project=False)
    assert lengths == {"a": pytest.approx(1), "b": pytest.approx(1)}


def test_prediction_tail_and_bh_are_monotone_and_handle_zero():
    assert MODULE.predictive_tail(0, 2.0, 0.5) == pytest.approx(1.0)
    assert MODULE.predictive_tail(10, 2.0, 0.5) < MODULE.predictive_tail(5, 2.0, 0.5)
    q = MODULE.bh_qvalues([0.01, 0.04, 0.20])
    assert q == pytest.approx([0.03, 0.06, 0.20])


def test_mesh_code_returns_eight_digits():
    assert MODULE.mesh_code(139.7671, 35.6812) == "53394611"


def test_moran_detects_clustered_and_alternating_values():
    coordinates = [(i, 0) for i in range(8)]
    clustered = [0, 0, 0, 0, 1, 1, 1, 1]
    alternating = [0, 1] * 4
    assert MODULE.moran_knn(clustered, coordinates, k=2, permutations=99)["i"] > 0
    assert MODULE.moran_knn(alternating, coordinates, k=2, permutations=99)["i"] < 0
