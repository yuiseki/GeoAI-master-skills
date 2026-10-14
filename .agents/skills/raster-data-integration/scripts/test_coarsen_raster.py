"""uvx --with rasterio --with pytest pytest test_coarsen_raster.py

Each 4 x 4 raster below is coarsened by 2; the expected 2 x 2 blocks are worked out by hand.
"""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from coarsen_raster import RESAMPLING, coarsen

ND = -1.0
COUNTS = [[1, 2, 3, 4],
          [5, 6, 7, 8],
          [9, ND, 11, 12],
          [13, 14, 15, 16]]
CLASSES = [[1, 1, 2, 2],
           [1, 1, 2, 2],
           [3, 3, 0, 2],
           [3, 9, 2, 2]]  # 0 is NoData. The lower-left block averages to 4.5, a class that does not exist


def write(path, rows, dtype, nodata):
    a = np.array(rows, dtype=dtype)
    with rasterio.open(path, "w", driver="GTiff", height=4, width=4, count=1, dtype=dtype, crs="EPSG:32654",
                       transform=from_origin(500000, 3950400, 100, 100), nodata=nodata) as d:
        d.write(a, 1)
    return str(path)


def read(path):
    with rasterio.open(path) as d:
        return d.read(1), d.nodata, d.transform.a


def test_extensive_blocks_are_sums_and_the_total_is_kept(tmp_path):
    out = tmp_path / "c.tif"
    coarsen(write(tmp_path / "in.tif", COUNTS, "float32", ND), "extensive", 2, str(out))
    a, nd, res = read(out)
    assert res == 200
    assert a.tolist() == [[14, 22], [36, 54]]  # 9 + 13 + 14: the NoData pixel adds nothing
    assert a.sum() == 126


def test_intensive_blocks_are_means_of_the_valid_pixels(tmp_path):
    out = tmp_path / "c.tif"
    coarsen(write(tmp_path / "in.tif", COUNTS, "float32", ND), "intensive", 2, str(out))
    a, _, _ = read(out)
    assert a.tolist() == [[3.5, 5.5], [12, 13.5]]  # (9 + 13 + 14) / 3, not / 4


def test_categorical_blocks_take_an_existing_class(tmp_path):
    out = tmp_path / "c.tif"
    coarsen(write(tmp_path / "in.tif", CLASSES, "uint8", 0), "categorical", 2, str(out))
    a, nd, _ = read(out)
    assert a.tolist() == [[1, 2], [3, 2]]
    assert set(a.flatten()) <= {1, 2, 3, 9}  # bilinear or average would make classes that do not exist


def test_an_all_nodata_block_stays_nodata(tmp_path):
    out = tmp_path / "c.tif"
    rows = [[ND, ND, 1, 1]] * 2 + [[1, 1, 1, 1]] * 2
    coarsen(write(tmp_path / "in.tif", rows, "float32", ND), "extensive", 2, str(out))
    a, nd, _ = read(out)
    assert a[0, 0] == nd and a[0, 1] == 4


def test_each_kind_has_one_fixed_resampling():
    assert RESAMPLING == {"extensive": "sum", "intensive": "average", "categorical": "mode"}


def test_a_factor_that_does_not_divide_keeps_the_total_in_partial_edge_blocks(tmp_path):
    out = tmp_path / "c.tif"
    coarsen(write(tmp_path / "in.tif", COUNTS, "float32", ND), "extensive", 3, str(out))
    a, nd, res = read(out)
    assert a.shape == (2, 2) and res == 300
    assert a.tolist() == [[1 + 2 + 3 + 5 + 6 + 7 + 9 + 11, 4 + 8 + 12], [13 + 14 + 15, 16]]


def test_kind_is_required(tmp_path):
    with pytest.raises(SystemExit):
        coarsen(write(tmp_path / "in.tif", COUNTS, "float32", ND), "mean", 2, str(tmp_path / "c.tif"))


def test_total_is_kept_exactly_on_a_degree_grid(tmp_path):
    # 3 arc-second pixels with the origin of a window cut from WorldPop's Japan grid. GDAL's warp with
    # resampling=sum lost 0.8 % of the total on this grid (rasterio 1.4.1, GDAL 3.9.2); a round origin lost nothing.
    rng = np.random.default_rng(0)
    a = rng.gamma(0.5, 20, (480, 600)).astype("float32")
    a[rng.random(a.shape) < 0.2] = ND
    src = tmp_path / "deg.tif"
    with rasterio.open(src, "w", driver="GTiff", height=480, width=600, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(139.49999872200002, 35.85000019259999, 0.00083333333, 0.00083333333), nodata=ND) as d:
        d.write(a, 1)
    out = tmp_path / "c.tif"
    coarsen(str(src), "extensive", 10, str(out))
    b, nd, _ = read(out)
    assert float(b[b != nd].sum()) == pytest.approx(float(a[a != ND].sum()), rel=1e-6)
    assert float(b[0, 0]) == pytest.approx(float(a[:10, :10][a[:10, :10] != ND].sum()), rel=1e-6)


def test_a_tie_between_classes_goes_to_the_smaller_code(tmp_path):
    out = tmp_path / "c.tif"
    rows = [[7, 7, 1, 1], [4, 4, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]  # the upper-left block is 7, 7, 4, 4
    coarsen(write(tmp_path / "in.tif", rows, "uint8", 0), "categorical", 2, str(out))
    a, _, _ = read(out)
    assert a[0, 0] == 4
