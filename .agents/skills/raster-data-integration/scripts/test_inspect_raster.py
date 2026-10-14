"""uvx --with rasterio --with pytest pytest test_inspect_raster.py"""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from inspect_raster import inspect

ND = -99999.0


def write(path, rows, dtype, nodata, crs="EPSG:32654", transform=None, scale=None, offset=None):
    a = np.array(rows, dtype=dtype)
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype=dtype,
                       crs=crs, transform=transform or from_origin(500000, 3950400, 100, 100), nodata=nodata) as d:
        d.write(a, 1)
        if scale:
            d.scales, d.offsets = (scale,), (offset or 0.0,)
    return str(path)


def test_counts_valid_nodata_and_zero_apart(tmp_path):
    r = inspect(write(tmp_path / "a.tif", [[0, 2, ND], [0, 5, ND]], "float32", ND))
    assert (r["pixels"], r["valid"], r["nodata"], r["zero"]) == (6, 4, 2, 2)
    assert (r["min"], r["max"], r["sum"]) == (0, 5, 7)


def test_nan_counts_as_missing_even_without_a_nodata_value(tmp_path):
    r = inspect(write(tmp_path / "a.tif", [[1, np.nan], [3, 4]], "float32", None))
    assert r["nodata_value"] is None
    assert (r["valid"], r["nan"]) == (3, 1)
    assert r["sum"] == 8


def test_grid_facts(tmp_path):
    r = inspect(write(tmp_path / "a.tif", [[1, 2, 3]] * 2, "float32", ND))
    assert r["crs"] == "EPSG:32654" and not r["geographic"]
    assert (r["height"], r["width"]) == (2, 3)
    assert r["resolution"] == (100, 100)
    assert r["bounds"] == (500000, 3950200, 500300, 3950400)
    assert r["dtype"] == "float32"


def test_geographic_pixel_size_is_also_given_in_metres(tmp_path):
    r = inspect(write(tmp_path / "g.tif", [[1, 1]] * 2, "float32", ND, crs="EPSG:4326",
                      transform=from_origin(139.0, 60.001, 0.001, 0.001)))
    assert r["geographic"]
    # 0.001 degree at 60N: about 111.4 m north-south, about 55.8 m east-west
    assert r["pixel_m_at_centre"][0] == pytest.approx(55.8, abs=0.5)
    assert r["pixel_m_at_centre"][1] == pytest.approx(111.4, abs=0.5)


def test_scale_and_offset_are_reported_and_applied_to_the_statistics(tmp_path):
    r = inspect(write(tmp_path / "s.tif", [[100, 200], [-32768, 300]], "int16", -32768, scale=0.1, offset=-5))
    assert (r["scale"], r["offset"]) == (0.1, -5)
    assert r["min"] == pytest.approx(5) and r["max"] == pytest.approx(25)


def test_integer_rasters_list_their_values(tmp_path):
    r = inspect(write(tmp_path / "c.tif", [[10, 20, 0], [20, 20, 30]], "uint8", 0))
    assert r["values"] == {10: 1, 20: 3, 30: 1}


def test_bbox_reads_only_that_window(tmp_path):
    p = write(tmp_path / "a.tif", [[1, 2, 3], [4, 5, 6]], "float32", ND)
    r = inspect(p, bbox=(500100, 3950200, 500300, 3950300))  # the lower right 2 pixels
    assert (r["pixels"], r["sum"]) == (2, 11)


def test_a_bbox_off_the_raster_stops_and_names_the_raster_crs(tmp_path):
    p = write(tmp_path / "a.tif", [[1, 2, 3], [4, 5, 6]], "float32", ND)
    with pytest.raises(SystemExit, match="EPSG:32654"):
        inspect(p, bbox=(139.5, 35.4, 140.0, 35.9))  # longitude and latitude given to a UTM raster
