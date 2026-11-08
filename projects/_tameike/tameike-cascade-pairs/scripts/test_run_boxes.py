"""uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with 'duckdb>=1.5.5' --with pytest pytest -q -p no:cacheprovider test_run_boxes.py"""

# The tile and grid helpers of run_boxes.py: tile_xy, fetch (cached files only), mosaic, utm_grid, to_utm.
import math
import os

# An anaconda GDAL_DATA / PROJ_LIB / PROJ_DATA in the shell points rasterio at an older proj.db (the scripts are run
# with env -u for the same reason); drop them before rasterio is imported.
for _k in ("GDAL_DATA", "PROJ_LIB", "PROJ_DATA"):
    os.environ.pop(_k, None)

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from pyproj import Transformer  # noqa: E402

import run_boxes as rb  # noqa: E402


def test_tile_xy():
    assert rb.tile_xy(0.0, 0.0, 1) == (1, 1)
    assert rb.tile_xy(-180.0, 85.0, 3) == (0, 0)
    # Kagawa box corner at z = 15: x = (133.78 + 180) / 360 * 2^15
    assert rb.tile_xy(133.78, 34.27, 15)[0] == int((133.78 + 180) / 360 * 2 ** 15)


def test_fetch_reads_cached_tiles_without_the_network(tmp_path, monkeypatch):
    monkeypatch.setattr(rb, "CACHE", tmp_path)
    (tmp_path / "dem5a").mkdir()
    (tmp_path / "dem5a" / "15_1_2.txt").write_text("1.5,e\n-2,3\n")
    (tmp_path / "dem5a" / "15_1_3.txt").write_text("")                 # a cached 404
    t = rb.fetch("dem5a", 15, 1, 2)
    assert t.dtype == np.float32 and t[0, 0] == 1.5 and np.isnan(t[0, 1]) and t[1].tolist() == [-2.0, 3.0]
    assert rb.fetch("dem5a", 15, 1, 3) is None


def test_mosaic_places_tiles_and_counts_missing_ones(monkeypatch):
    box = rb.BOXES["kagawa"]
    z = rb.LAYERS["dem"]
    x0, y0 = rb.tile_xy(box[0], box[3], z)
    x1, y1 = rb.tile_xy(box[2], box[1], z)

    def fake(layer, zz, x, y):
        return None if (x, y) == (x0, y0) else np.full((256, 256), float(x - x0 + 10 * (y - y0)), "float32")

    monkeypatch.setattr(rb, "fetch", fake)
    arr, tr, info = rb.mosaic("dem", box)
    assert arr.shape == ((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256)
    assert info == {"tiles": (x1 - x0 + 1) * (y1 - y0 + 1), "tiles_404": 1}
    assert np.isnan(arr[0, 0]) and arr[0, 256] == 1.0 and arr[256, 0] == 10.0
    m = 2 * math.pi * 6378137 / 2 ** z
    assert tr.a == pytest.approx(m / 256) and tr.c == pytest.approx(x0 * m - math.pi * 6378137)


def test_utm_grid_lies_inside_the_box_on_10m_steps():
    box = rb.BOXES["awaji"]
    (h, w), tr = rb.utm_grid(box, 5.0)
    assert tr.a == 5.0 and tr.e == -5.0 and tr.c % 10 == 0 and tr.f % 10 == 0
    t = Transformer.from_crs(rb.DST, "EPSG:4326", always_xy=True)
    lon, lat = t.transform([tr.c, tr.c + w * 5, tr.c, tr.c + w * 5], [tr.f, tr.f, tr.f - h * 5, tr.f - h * 5])
    # inside the lon/lat box up to the 10 m snapping of the west edge (well under 0.001 degree)
    assert min(lon) >= box[0] - 1e-3 and max(lon) <= box[2] and min(lat) >= box[1] and max(lat) <= box[3]
    assert 14_000 < w * 5 < 15_000 and 15_000 < h * 5 < 16_000      # about 0.16 x 0.14 degrees


def test_to_utm_keeps_holes_as_nan():
    box = rb.BOXES["awaji"]
    z = rb.LAYERS["dem5a"]
    x0, y0 = rb.tile_xy(box[0], box[3], z)
    m = 2 * math.pi * 6378137 / 2 ** z
    o = math.pi * 6378137
    from rasterio.transform import from_bounds
    arr = np.full((256, 256), 12.0, "float32")
    arr[100:140, 100:140] = np.nan
    tr = from_bounds(x0 * m - o, o - (y0 + 1) * m, (x0 + 1) * m - o, o - y0 * m, 256, 256)
    # a 5 m UTM grid over the middle of this tile
    to = Transformer.from_crs("EPSG:3857", rb.DST, always_xy=True)
    cx, cy = to.transform(x0 * m - o + 120 * m / 256, o - y0 * m - 120 * m / 256)
    from rasterio.transform import from_origin
    grid = ((20, 20), from_origin(cx - 50, cy + 50, 5, 5))
    out = rb.to_utm(arr, tr, grid)
    assert np.isnan(out).all()                       # the centre of the hole
    grid2 = ((10, 10), from_origin(cx - 400, cy + 400, 5, 5))
    out2 = rb.to_utm(arr, tr, grid2)
    assert np.allclose(out2, 12.0)                   # outside the hole the elevation is kept
