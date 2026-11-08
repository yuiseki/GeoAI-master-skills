"""uvx --python 3.12 --with numpy --with pandas --with scipy --with 'duckdb>=1.5.5' --with shapely --with matplotlib --with pytest pytest -q -p no:cacheprovider test_analyze.py"""

# top, overlap and rho of analyze.py; polygons_from_wkt and zoom_rect of make_figures.py.
# Both modules create their own outputs/ folder at import (mkdir exist_ok); the folder is tracked and nothing is written.
import numpy as np
import pandas as pd
import pytest

import analyze as an
import make_figures as mf


def frame():
    return pd.DataFrame({"mesh1kmid": ["m3", "m1", "m2", "m4"], "day": [5.0, 5.0, 1.0, 9.0], "night": [1.0, 2.0, 3.0, np.nan]})


def test_top_sorts_by_value_then_mesh_id():
    assert an.top(frame(), "day", n=3).mesh1kmid.tolist() == ["m4", "m1", "m3"]


def test_overlap_counts_common_meshes():
    f = frame()
    assert an.overlap(an.top(f, "day", 2), an.top(f, "night", 2)) == 1      # {m4, m1} & {m2, m1}; NaN sorts last
    assert an.overlap(an.top(f, "day", 3), an.top(f, "night", 3)) == 2      # {m4, m1, m3} & {m2, m1, m3}


def test_rho_drops_missing_and_needs_three_pairs():
    f = frame()
    # complete pairs m3, m1, m2: day [5, 5, 1], night [1, 2, 3]: ranks [2.5, 2.5, 1] and [1, 2, 3] -> -0.866
    assert an.rho(f.day, f.night) == pytest.approx(-np.sqrt(3) / 2)
    assert an.rho(f.day.iloc[:2], f.night.iloc[:2]) is None


def test_polygons_from_wkt_splits_multipolygons_and_repairs_bowties():
    assert len(mf.polygons_from_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")) == 1
    assert len(mf.polygons_from_wkt("MULTIPOLYGON(((0 0, 1 0, 1 1, 0 0)), ((5 5, 6 5, 6 6, 5 5)))")) == 2
    bowtie = mf.polygons_from_wkt("POLYGON((0 0, 2 2, 2 0, 0 2, 0 0))")
    assert len(bowtie) == 2 and sum(p.area for p in bowtie) == pytest.approx(2.0)
    assert mf.polygons_from_wkt("LINESTRING(0 0, 1 1)") == []


def test_zoom_rect_pads_the_bounds_of_meshes_in_the_window():
    lon = (mf.ZOOM_LON[0] + mf.ZOOM_LON[1]) / 2
    lat = (mf.ZOOM_LAT[0] + mf.ZOOM_LAT[1]) / 2
    f = pd.DataFrame({"mesh1kmid": ["a", "b", "c"], "lon": [lon, lon, mf.ZOOM_LON[1] + 1], "lat": [lat, lat, lat]})
    sq = lambda x, y: mf.polygons_from_wkt(f"POLYGON(({x} {y}, {x + 1000} {y}, {x + 1000} {y + 1000}, {x} {y + 1000}, {x} {y}))")
    shapes = {"a": sq(0, 0), "b": sq(1000, 2000), "c": sq(90000, 90000)}
    assert mf.zoom_rect(f, shapes, None, None) == (-500.0, -500.0, 2500.0, 3500.0)
