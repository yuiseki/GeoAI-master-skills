"""uvx --with rasterio --with affine --with numpy --with pyproj --with pytest pytest test_raster_to_grid.py

Expected values are worked out by hand from rasters of a few pixels, and the end-to-end runs write small GeoTIFFs.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# an anaconda install on the author's machine sets these for its own GDAL; the rasterio wheel must not see them
# (the scripts it runs inherit this environment)
for _k in ("GDAL_DATA", "GDAL_DRIVER_PATH", "PROJ_DATA", "PROJ_LIB", "PROJ_NETWORK"):
    os.environ.pop(_k, None)

import numpy as np
import pytest
from affine import Affine

import raster_to_grid as rg

HERE = Path(__file__).parent


def test_pixel_centres_follow_the_affine_transform():
    lon, lat = rg.pixel_centres(Affine(0.5, 0, 100.0, 0, -0.5, 50.0), row0=2, nrows=2, col0=1, ncols=3)
    assert lon[0, 0] == 100.75 and lat[0, 0] == 48.75 and lon[0, 2] == 101.75 and lat[1, 0] == 48.25
    with pytest.raises(ValueError):
        rg.pixel_centres(Affine(0.5, 0.1, 100.0, 0, -0.5, 50.0), 0, 1, 0, 1)


def test_classes_nodata_and_off_grid_are_kept_apart():
    acc = rg.ClassAcc(rg.GridSpec(0, 0, 2, 1, 100), classes=[10, 40])
    acc.add(np.array([10, 10, 40, 40, 0, 10]), np.array([10, 20, 30, 150, 160, 999]), np.array([10] * 6), nodata=0)
    assert acc.counts[10][0, 0] == 2 and acc.counts[40][0, 0] == 1 and acc.counts[40][0, 1] == 1
    assert acc.nodata[0, 1] == 1 and acc.off_grid == 1
    assert acc.fractions()[10][0, 0] == 2 / 3 and acc.fractions()[40][0, 1] == 1.0


def test_sum_keeps_the_total_and_mean_leaves_empty_cells_nan():
    s = rg.SumAcc(rg.GridSpec(0, 0, 2, 1, 100))
    s.add(np.array([1.5, 2.0, -99999.0, 4.0]), np.array([10, 150, 150, 500]), np.array([10] * 4), nodata=-99999.0)
    assert s.total[0, 0] == 1.5 and s.total[0, 1] == 2.0 and s.off_grid_total == 4.0 and s.nodata[0, 1] == 1
    m = rg.MeanAcc(rg.GridSpec(0, 0, 2, 1, 100))
    m.add(np.array([100.0, 200.0, np.nan]), np.array([10, 20, 30]), np.array([10, 10, 10]), nodata=None)
    assert m.mean()[0, 0] == 150.0 and np.isnan(m.mean()[0, 1]) and m.nodata[0, 0] == 1


def write_tif(path, arr, transform, crs, nodata):
    import rasterio

    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1, dtype=arr.dtype,
                       crs=crs, transform=transform, nodata=nodata) as dst:
        dst.write(arr, 1)


def run(args):
    return subprocess.run([sys.executable, str(HERE / "raster_to_grid.py")] + args, capture_output=True, text=True)


def test_end_to_end_sum_in_the_same_crs(tmp_path):
    # 4 x 4 pixels of 50 m on a grid of 100 m cells: each cell gets 4 pixels
    arr = np.arange(16, dtype=np.float32).reshape(4, 4)
    arr[0, 0] = -1
    write_tif(tmp_path / "r.tif", arr, Affine(50, 0, 0, 0, -50, 200), "EPSG:6678", -1)
    json.dump({"x0": 0, "y0": 0, "nx": 2, "ny": 2, "size": 100, "crs": "EPSG:6678"}, open(tmp_path / "g.json", "w"))
    r = run([str(tmp_path / "r.tif"), str(tmp_path / "g.json"), "--kind", "sum", "--out", str(tmp_path / "o.npz")])
    assert r.returncode == 0, r.stderr
    o = np.load(tmp_path / "o.npz")
    # grid row 1 (north) holds raster rows 0-1; the north-west cell has 1 + 4 + 5 (0,0 is NoData)
    assert o["total"][1, 0] == 1 + 4 + 5 and o["total"][0, 1] == 10 + 11 + 14 + 15
    assert o["nodata"][1, 0] == 1 and (o["pixels"] == 4).all()


def test_end_to_end_class_from_lon_lat_keeps_every_pixel(tmp_path):
    # a lon/lat raster near Akita moved into EPSG:6678: every pixel lands on the grid or is counted off it
    rng = np.random.default_rng(0)
    arr = rng.choice(np.array([10, 40, 80], dtype=np.uint8), size=(60, 60))
    write_tif(tmp_path / "c.tif", arr, Affine(0.001, 0, 140.0, 0, -0.001, 39.8), "EPSG:4326", 0)
    import pyproj

    x, y = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True).transform([140.0, 140.06], [39.74, 39.8])
    g = {"x0": float(np.floor(min(x) / 100) * 100), "y0": float(np.floor(min(y) / 100) * 100), "nx": 60, "ny": 80, "size": 100, "crs": "EPSG:6678"}
    json.dump(g, open(tmp_path / "g.json", "w"))
    r = run([str(tmp_path / "c.tif"), str(tmp_path / "g.json"), "--kind", "class", "--classes", "10", "40", "80", "--out", str(tmp_path / "o.npz")])
    assert r.returncode == 0, r.stderr
    o = np.load(tmp_path / "o.npz")
    off = int(r.stdout.split("pixels off the grid ")[1].split()[0])
    assert int(o["pixels"].sum()) + off == 3600
    assert int(o["valid"].sum()) == int(o["pixels"].sum())  # no NoData drawn
    f = np.nan_to_num(o["f10"]) + np.nan_to_num(o["f40"]) + np.nan_to_num(o["f80"])
    assert np.allclose(f[o["valid"] > 0], 1.0)


def test_class_needs_the_list_of_classes(tmp_path):
    write_tif(tmp_path / "c.tif", np.ones((2, 2), np.uint8), Affine(50, 0, 0, 0, -50, 100), "EPSG:6678", 0)
    json.dump({"x0": 0, "y0": 0, "nx": 1, "ny": 1, "size": 100, "crs": "EPSG:6678"}, open(tmp_path / "g.json", "w"))
    assert run([str(tmp_path / "c.tif"), str(tmp_path / "g.json"), "--kind", "class", "--out", str(tmp_path / "o.npz")]).returncode != 0
