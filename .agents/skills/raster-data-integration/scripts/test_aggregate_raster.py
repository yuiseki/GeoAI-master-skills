"""uvx --from 'duckdb>=1.5.5' --with rasterio --with shapely --with pyproj --with pyarrow --with pytest pytest test_aggregate_raster.py

Expected values are worked out by hand from the 4 x 4 rasters drawn below, not with the code under test.
"""

import duckdb
import numpy as np
import pyproj
import pytest
import rasterio
import shapely
from rasterio.transform import from_origin

from aggregate_raster import aggregate

ND = -1.0
X0, Y0 = 500000.0, 3950400.0  # UTM 54N (EPSG:32654), 100 m pixels, rows top to bottom
COUNTS = [[1, 2, 3, 4],
          [5, 6, 7, 8],
          [9, ND, 11, 12],
          [13, 14, 15, 16]]  # 136 - 10 = 126 people in the 15 valid pixels
CLASSES = [[1, 1, 2, 2],
           [1, 1, 2, 2],
           [3, 3, 0, 2],
           [3, 3, 2, 2]]  # 0 is NoData


def sq(x1, y1, x2, y2):
    """A rectangle in metres from the raster's top-left corner (x right, y down)."""
    return shapely.box(X0 + x1, Y0 - y2, X0 + x2, Y0 - y1)


UNITS = {
    "left": sq(0, 0, 200, 400),        # columns 0-1: 1,2,5,6,9,ND,13,14
    "right": sq(200, 0, 400, 400),     # columns 2-3: 3,4,7,8,11,12,15,16
    "away": sq(1000, 0, 1100, 100),    # one pixel's worth entirely east of the raster
    "edge": sq(300, 0, 500, 100),      # pixel (0,3) = 4, and one pixel east of the raster
    "corner": sq(0, 0, 140, 140),      # centre rule: (0,0) only. Area: 1 + 0.4 + 0.4 + 0.16 of pixels
    "tiny": sq(10, 10, 40, 40),        # holds no pixel centre
}


def write_raster(path, rows, dtype, nodata, crs="EPSG:32654", transform=None, scale=None):
    a = np.array(rows, dtype=dtype)
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype=dtype,
                       crs=crs, transform=transform or from_origin(X0, Y0, 100, 100), nodata=nodata) as d:
        d.write(a, 1)
        if scale:
            d.scales = (scale,)
    return str(path)


def write_units(path, units, crs="EPSG:32654"):
    to = pyproj.Transformer.from_crs("EPSG:32654", crs, always_xy=True)
    rows = ", ".join(f"('{k}', '{shapely.transform(g, lambda c: np.column_stack(to.transform(c[:, 0], c[:, 1]))).wkt}')"
                     for k, g in units.items())
    duckdb.sql(f"copy (select id, wkt from (values {rows}) t(id, wkt)) to '{path}' (format parquet)")
    return str(path)


def rows_of(out):
    con = duckdb.connect()
    cols = [c[0] for c in con.sql(f"describe select * from '{out}'").fetchall()]
    return {r[0]: dict(zip(cols, r)) for r in con.sql(f"select * from '{out}'").fetchall()}


@pytest.fixture
def counts(tmp_path):
    return write_raster(tmp_path / "counts.tif", COUNTS, "float32", ND)


def run(tmp_path, raster, units, kind, **kw):
    out = tmp_path / f"out_{kind}.parquet"
    report = aggregate(raster, write_units(tmp_path / "units.parquet", units, kw.pop("units_crs", "EPSG:32654")),
                       "id", kind, str(out), units_crs=kw.pop("crs_arg", "EPSG:32654"), geom="wkt", **kw)
    return rows_of(out), report


def test_sum_counts_only_valid_pixels_inside_each_unit(tmp_path, counts):
    r, _ = run(tmp_path, counts, UNITS, "extensive")
    assert r["left"]["sum"] == pytest.approx(50)
    assert r["right"]["sum"] == pytest.approx(76)
    assert r["left"]["cells_valid"] == 7 and r["left"]["cells_nodata"] == 1  # the ND pixel is not a 0
    assert r["right"]["cells_nodata"] == 0


def test_mean_leaves_nodata_out_instead_of_counting_it_as_zero(tmp_path, counts):
    r, _ = run(tmp_path, counts, UNITS, "intensive")
    assert r["left"]["mean"] == pytest.approx(50 / 7)  # 6.25 if the NoData pixel were a 0
    assert (r["left"]["min"], r["left"]["max"]) == (1, 14)


def test_every_unit_gets_a_row_with_its_coverage(tmp_path, counts):
    r, _ = run(tmp_path, counts, UNITS, "extensive")
    assert set(r) == set(UNITS)
    assert r["away"]["status"] == "outside_raster" and r["away"]["sum"] is None
    assert r["away"]["cells_outside"] == 1
    assert r["edge"]["sum"] == pytest.approx(4) and r["edge"]["cells_outside"] == 1
    assert r["tiny"]["status"] == "no_pixel_centre" and r["tiny"]["sum"] is None


def test_centre_rule_excludes_pixels_whose_centre_is_outside_the_unit(tmp_path, counts):
    r, _ = run(tmp_path, counts, {"corner": UNITS["corner"]}, "extensive")
    assert r["corner"]["sum"] == pytest.approx(1)  # 14 if every touched pixel were taken


def test_fraction_rule_weights_pixels_by_the_share_of_their_area_inside(tmp_path, counts):
    r, _ = run(tmp_path, counts, {"corner": UNITS["corner"], "tiny": UNITS["tiny"]}, "extensive", method="fraction")
    assert r["corner"]["sum"] == pytest.approx(1 * 1 + 2 * 0.4 + 5 * 0.4 + 6 * 0.16)
    assert r["tiny"]["sum"] == pytest.approx(1 * 0.09)
    assert r["corner"]["area_valid_km2"] == pytest.approx(0.0196, rel=1e-6)  # 140 m x 140 m


def test_total_is_conserved_when_units_tile_the_raster(tmp_path, counts):
    _, rep = run(tmp_path, counts, {"left": UNITS["left"], "right": UNITS["right"]}, "extensive")
    assert rep["raster_total_in_units"] == pytest.approx(126)
    assert rep["assigned_total"] == pytest.approx(126)
    assert rep["ok"]


def test_overlapping_units_are_reported_as_counted_twice(tmp_path, counts):
    units = {"left": UNITS["left"], "right": UNITS["right"], "edge": UNITS["edge"]}  # edge repeats pixel (0,3) = 4
    _, rep = run(tmp_path, counts, units, "extensive")
    assert rep["assigned_total"] == pytest.approx(130)
    assert rep["raster_total_in_units"] == pytest.approx(126)
    assert rep["counted_twice"] == pytest.approx(4)
    assert not rep["ok"]


def test_units_in_another_crs_are_moved_onto_the_raster(tmp_path, counts):
    r, _ = run(tmp_path, counts, {"left": UNITS["left"], "right": UNITS["right"]}, "extensive",
               units_crs="EPSG:4326", crs_arg="EPSG:4326")
    assert r["left"]["sum"] == pytest.approx(50) and r["right"]["sum"] == pytest.approx(76)


def test_wrong_units_crs_is_not_silently_accepted(tmp_path, counts):
    # lon/lat polygons declared as metres land nowhere near the raster: every unit is outside, and it says so
    r, _ = run(tmp_path, counts, {"left": UNITS["left"]}, "extensive", units_crs="EPSG:4326", crs_arg="EPSG:32654")
    assert r["left"]["status"] == "outside_raster"


def test_categorical_shares_ignore_nodata(tmp_path):
    raster = write_raster(tmp_path / "classes.tif", CLASSES, "uint8", 0)
    r, _ = run(tmp_path, raster, {"left": UNITS["left"], "right": UNITS["right"]}, "categorical")
    assert r["left"]["class_1"] == pytest.approx(0.5) and r["left"]["class_3"] == pytest.approx(0.5)
    assert r["left"]["class_2"] == pytest.approx(0)
    assert r["right"]["class_2"] == pytest.approx(1.0) and r["right"]["cells_nodata"] == 1
    assert r["left"]["majority"] == 1  # a tie goes to the smaller class


def test_scale_is_applied_before_aggregating(tmp_path):
    raster = write_raster(tmp_path / "scaled.tif", [[10, 20, 30, 40]] * 4, "int16", -32768, scale=0.1)
    r, _ = run(tmp_path, raster, {"left": UNITS["left"]}, "intensive")
    assert r["left"]["mean"] == pytest.approx(1.5)  # (1 + 2) / 2, not (10 + 20) / 2


def test_pixel_area_follows_latitude_on_a_geographic_raster(tmp_path):
    # Two 1-degree rows: one at the equator, one at 60-61N. Same value, so the sums show the areas.
    t = from_origin(0, 61, 1, 1)
    rows = [[1.0]] + [[ND]] * 59 + [[1.0]]
    raster = write_raster(tmp_path / "geo.tif", rows, "float32", ND, crs="EPSG:4326", transform=t)
    con = duckdb.connect()
    out = tmp_path / "geo.parquet"
    units = tmp_path / "geo_units.parquet"
    con.sql(f"copy (select * from (values ('north', 'POLYGON((0 60, 1 60, 1 61, 0 61, 0 60))'),"
            f" ('equator', 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))')) t(id, wkt)) to '{units}' (format parquet)")
    aggregate(raster, str(units), "id", "extensive", str(out), units_crs="EPSG:4326", geom="wkt")
    r = rows_of(out)
    assert r["equator"]["area_valid_km2"] == pytest.approx(12308, rel=0.01)  # 110.6 km x 111.3 km
    assert r["north"]["area_valid_km2"] / r["equator"]["area_valid_km2"] == pytest.approx(0.49, abs=0.01)  # cos 60.5


def test_duplicate_unit_ids_stop(tmp_path, counts):
    units = tmp_path / "dup.parquet"
    duckdb.sql(f"copy (select * from (values ('a', 'POINT(0 0)'), ('a', 'POINT(1 1)')) t(id, wkt)) to '{units}' (format parquet)")
    with pytest.raises(SystemExit):
        aggregate(counts, str(units), "id", "extensive", str(tmp_path / "x.parquet"), units_crs="EPSG:32654", geom="wkt")


def test_points_take_the_value_of_the_pixel_they_fall_in(tmp_path, counts):
    pts = {"p6": shapely.Point(X0 + 150, Y0 - 150),       # pixel (1, 1) = 6
           "p_nd": shapely.Point(X0 + 150, Y0 - 250),     # pixel (2, 1) is NoData
           "p_out": shapely.Point(X0 + 450, Y0 - 50),     # east of the raster
           "p_edge": shapely.Point(X0 + 200, Y0 - 50)}    # on the line between pixels (0, 1) and (0, 2): the east one, 3
    r, _ = run(tmp_path, counts, pts, "intensive")
    assert r["p6"]["mean"] == 6 and r["p6"]["status"] == "ok"
    assert r["p_nd"]["status"] == "no_valid_pixels" and r["p_nd"]["mean"] is None
    assert r["p_out"]["status"] == "outside_raster"
    assert r["p_edge"]["mean"] == 3


def test_lines_are_refused_rather_than_guessed(tmp_path, counts):
    r, _ = run(tmp_path, counts, {"line": shapely.LineString([(X0 + 50, Y0 - 50), (X0 + 350, Y0 - 50)])}, "extensive")
    assert r["line"]["status"] == "unsupported_geometry"
