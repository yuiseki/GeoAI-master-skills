"""uvx --with numpy --with scipy --with scikit-image --with rasterio --with pytest pytest -q test_sar_change.py

Small rasters whose answers are worked out by hand, not with the code under test.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sar_change  # noqa: E402

HERE = Path(__file__).resolve().parent


def test_boxcar_mean_ignores_nan():
    a = np.ones((5, 5))
    a[2, 2] = np.nan
    a[0, 0] = 10.0
    b = sar_change.boxcar(a, 3)
    assert b[2, 2] == pytest.approx(1.0)  # 8 valid neighbours, all 1
    assert b[0, 0] == pytest.approx((10 + 1 + 1 + 1) / 4)  # a corner sees 4 pixels
    assert sar_change.boxcar(a, 1)[0, 0] == 10.0  # k = 1 is no smoothing


def test_boxcar_all_nan_stays_nan():
    assert np.isnan(sar_change.boxcar(np.full((3, 3), np.nan), 3)).all()


def test_ratio_db():
    assert sar_change.ratio_db(np.array([0.5]), np.array([1.0]))[0] == pytest.approx(-3.0103, abs=1e-4)
    assert sar_change.ratio_db(np.array([2.0]), np.array([1.0]))[0] == pytest.approx(3.0103, abs=1e-4)


def test_change_db_averages_pre_in_linear_power_not_db():
    # two pre scenes 0.1 and 0.3: the linear mean is 0.2, the dB mean would be 10 log10(sqrt(0.03)) = -7.61
    pre = [np.full((3, 3), 0.1), np.full((3, 3), 0.3)]
    post = np.full((3, 3), 0.2)
    d = sar_change.change_db(pre, post, k=1)
    assert np.allclose(d, 0.0)


def test_change_db_smooths_before_the_ratio():
    # speckle-like checkerboard of 0.5 and 1.5 in post, pre flat 1: the 3x3 mean at the centre is (5*0.5+4*1.5)/9
    post = np.where((np.indices((3, 3)).sum(0) % 2) == 0, 0.5, 1.5)
    d = sar_change.change_db([np.ones((3, 3))], post, k=3)
    assert d[1, 1] == pytest.approx(10 * np.log10((5 * 0.5 + 4 * 1.5) / 9))


def test_shift_against_mask_recovers_known_shift():
    rng = np.random.default_rng(3)
    water = np.zeros((200, 200), bool)
    water[60:90, 40:160] = True
    water[120:180, 100:130] = True
    db = np.where(water, -22.0, -8.0) + rng.normal(0, 1.0, water.shape)
    shifted = np.roll(np.roll(db, 2, axis=0), -3, axis=1)  # the image lies 2 rows down, 3 cols left of the mask
    s = sar_change.shift_against_mask(shifted, water)
    assert s[0] == pytest.approx(-2, abs=0.3)
    assert s[1] == pytest.approx(3, abs=0.3)
    back = sar_change.apply_int_shift(shifted, s)
    assert np.nanmean(np.abs(back[10:-10, 10:-10] - db[10:-10, 10:-10])) < 1e-9


def test_apply_int_shift_fills_nan():
    a = np.arange(16, dtype=float).reshape(4, 4)
    b = sar_change.apply_int_shift(a, (1, 0))
    assert np.isnan(b[0]).all()
    assert (b[1] == a[0]).all()


def write(path, a, transform=from_origin(500000, 4000000, 10, 10), crs="EPSG:32654", nodata=-32768.0):
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype="float32",
                       crs=crs, transform=transform, nodata=nodata) as dst:
        dst.write(a.astype("float32"), 1)


def run(*args):
    out = subprocess.run([sys.executable, str(HERE / "sar_change.py"), *map(str, args)], capture_output=True, text=True)
    return out


def test_cli_writes_db_change_and_counts_every_pixel(tmp_path):
    pre = np.full((20, 20), 0.1)
    post = pre.copy()
    post[5:10, 5:10] = 0.01  # -10 dB: open water
    post[12:16, 12:16] = 0.4  # +6.02 dB: double bounce
    pre_nd = pre.copy()
    pre_nd[0, 0] = -32768  # NoData in one pre scene only: the other pre scene still covers it
    post[19, 19] = -32768  # NoData in post: no change there
    write(tmp_path / "pre1.tif", pre_nd)
    write(tmp_path / "pre2.tif", pre)
    write(tmp_path / "post.tif", post)
    r = run("--pre", tmp_path / "pre1.tif", tmp_path / "pre2.tif", "--post", tmp_path / "post.tif",
            "--k", 1, "--threshold", 3, "--out", tmp_path / "d.tif")
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout)
    assert s["pixels"] == 400
    assert s["valid"] == 399 and s["no_post"] == 1 and s["no_pre"] == 0
    assert s["darker"] == 25 and s["brighter"] == 16
    with rasterio.open(tmp_path / "d.tif") as src:
        d = src.read(1)
        assert src.crs.to_epsg() == 32654
    assert d[7, 7] == pytest.approx(-10.0, abs=1e-4)
    assert d[13, 13] == pytest.approx(6.0206, abs=1e-4)
    assert np.isnan(d[19, 19])
    assert d[0, 0] == pytest.approx(0.0)


def test_cli_stops_when_grids_differ(tmp_path):
    a = np.full((10, 10), 0.1)
    write(tmp_path / "pre.tif", a)
    write(tmp_path / "post.tif", a, transform=from_origin(500010, 4000000, 10, 10))
    r = run("--pre", tmp_path / "pre.tif", "--post", tmp_path / "post.tif", "--out", tmp_path / "d.tif")
    assert r.returncode != 0
    assert "grid" in r.stderr


def test_cli_measures_and_shifts_against_water(tmp_path):
    rng = np.random.default_rng(0)
    water = np.zeros((120, 120), bool)
    water[30:50, 20:100] = True
    water[70:110, 60:80] = True
    lin = np.where(water, 0.005, 0.1) * rng.gamma(20, 1 / 20, water.shape)
    img = np.roll(lin, 2, axis=1)  # the image lies 2 cols east of the mask
    write(tmp_path / "pre.tif", img)
    write(tmp_path / "post.tif", img)
    with rasterio.open(tmp_path / "w.tif", "w", driver="GTiff", height=120, width=120, count=1, dtype="uint8",
                       crs="EPSG:32654", transform=from_origin(500000, 4000000, 10, 10)) as dst:
        dst.write(water.astype("uint8"), 1)
    r = run("--pre", tmp_path / "pre.tif", "--post", tmp_path / "post.tif", "--water", tmp_path / "w.tif",
            "--out", tmp_path / "d.tif")
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout)
    assert s["pre_vs_water_shift_rows_cols"][1] == pytest.approx(-2, abs=0.3)
    assert s["shift_applied_rows_cols"] == [0, -2]
    assert s["post_vs_pre_shift_rows_cols"] == [pytest.approx(0, abs=0.1), pytest.approx(0, abs=0.1)]
    with rasterio.open(tmp_path / "d.tif") as src:
        d = src.read(1)
    assert np.isnan(d[:, -2:]).all()  # nothing lands in the last 2 columns after moving 2 to the west
