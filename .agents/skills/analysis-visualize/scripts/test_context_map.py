"""uvx --with numpy --with duckdb --with shapely --with matplotlib --with pytest pytest test_context_map.py"""

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import shapely
from context_map import (
    areas_containing,
    aspect,
    check_context_crs,
    fit_grid,
    label_areas,
    text_overlaps,
)

STEP = 2 / 225


def _centres(cells, lon0=143.0, lat0=46.0):
    rows = np.array([r for r, _ in cells])
    cols = np.array([c for _, c in cells])
    return rows, cols, lon0 + (cols + 0.5) * STEP, lat0 - (rows + 0.5) * STEP


def test_geographic_maps_are_stretched_by_latitude_and_projected_maps_are_not():
    assert aspect("EPSG:4326", 43, 44) == pytest.approx(1 / math.cos(math.radians(43.5)))
    assert aspect("OGC:CRS84", -10, 10) == pytest.approx(1.0)
    assert aspect("EPSG:6668", 35, 36) == pytest.approx(1 / math.cos(math.radians(35.5)))
    assert aspect("EPSG:6677", 0, 100000) == 1.0


def test_grid_is_recovered_from_centres_and_squares_tile_without_gaps():
    rows, cols, x, y = _centres([(1, 1), (3, 4), (2, 7)])
    grid = fit_grid(rows, cols, x, y)
    assert grid["step"] == pytest.approx(STEP)
    sq = grid["squares"]
    assert sq[0].bounds == pytest.approx((143 + STEP, 46 - 2 * STEP, 143 + 2 * STEP, 46 - STEP))
    assert all(s.area == pytest.approx(STEP ** 2) for s in sq)
    one_row = fit_grid(*_centres([(1, 1), (1, 2)]))
    assert not one_row["square_checked"]
    a = one_row["squares"]
    assert a[0].touches(a[1]) and a[0].intersection(a[1]).length == pytest.approx(STEP)


def test_grid_stops_when_a_centre_is_off_the_grid_or_cells_are_not_square():
    rows, cols, x, y = _centres([(1, 1), (2, 2), (3, 5)])
    x[1] += STEP / 10
    with pytest.raises(ValueError, match="off the grid"):
        fit_grid(rows, cols, x, y)
    rows, cols, x, y = _centres([(1, 1), (2, 2), (3, 5)])
    with pytest.raises(ValueError, match="square"):
        fit_grid(rows, cols, x, 46 - (rows + 0.5) * STEP * 2)


def test_context_layer_in_another_crs_stops_unless_the_difference_is_declared():
    check_context_crs("EPSG:4326", "EPSG:4326", None)
    with pytest.raises(SystemExit, match="EPSG:4612"):
        check_context_crs("EPSG:4326", "EPSG:4612", None)
    assert "1 m" in check_context_crs("EPSG:4326", "EPSG:4612", "JGD2000 and WGS84 differ by about 1 m")


def test_every_area_holding_a_point_is_named_because_boundaries_overlap():
    areas = [("A", shapely.box(0, 0, 1, 1)), ("B", shapely.box(1, 0, 2, 1)), ("C", shapely.box(5, 5, 6, 6))]
    assert areas_containing(shapely.Point(0.5, 0.5), areas) == "A"
    assert areas_containing(shapely.Point(1.0, 0.5), areas) == "A/B"
    assert areas_containing(shapely.Point(3, 3), areas) == ""


def _ax():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    return fig, ax


def test_only_areas_large_enough_and_inside_the_view_get_a_name():
    fig, ax = _ax()
    areas = [("big", shapely.box(1, 1, 6, 6)), ("tiny", shapely.box(7, 7, 7.1, 7.1)),
             ("outside", shapely.box(20, 20, 30, 30))]
    texts = label_areas(ax, areas, (0, 10, 0, 10), min_share=0.01)
    assert [t.get_text() for t in texts] == ["big"]


def test_overlapping_texts_and_a_text_under_the_legend_are_reported():
    from matplotlib.patches import Patch

    fig, ax = _ax()
    a = ax.text(5, 5, "AAAA", fontsize=12)
    b = ax.text(5.2, 5.1, "BBBB", fontsize=12)
    c = ax.text(1, 9, "CCCC", fontsize=12)
    d = ax.text(9.5, 0.5, "DDDD", fontsize=12, ha="right")
    leg = ax.legend(handles=[Patch(label="legend entry")], loc="lower right")
    found = text_overlaps(fig, [a, b, c, d], [leg])
    assert ("AAAA", "BBBB") in found
    assert ("DDDD", "legend") in found
    assert not any("CCCC" in pair for pair in found)


def test_cli_turns_cell_centres_into_squares(tmp_path):
    import duckdb

    rows, cols, x, y = _centres([(1, 1), (1, 2), (2, 1)])
    csv = tmp_path / "cells.csv"
    csv.write_text("id,r,c,lon,lat,v\n" + "".join(f"{i},{r},{c},{a},{b},{i * 1.5}\n"
                                                  for i, (r, c, a, b) in enumerate(zip(rows, cols, x, y))))
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("context_map.py")), "squares", str(csv),
                          "--row", "r", "--col", "c", "--x", "lon", "--y", "lat", "--out", str(tmp_path / "sq.parquet")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    con = duckdb.connect()
    con.sql("load spatial")
    got = con.sql(f"select id, v, ST_Area(geometry) from '{tmp_path / 'sq.parquet'}' order by id").fetchall()
    assert [g[0] for g in got] == [0, 1, 2] and got[2][1] == 3.0
    assert all(g[2] == pytest.approx(STEP ** 2) for g in got)
