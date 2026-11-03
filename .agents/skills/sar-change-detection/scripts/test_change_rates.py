"""uvx --with numpy --with scipy --with rasterio --with pytest pytest -q test_change_rates.py

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
import change_rates  # noqa: E402

HERE = Path(__file__).resolve().parent


def test_standardized_rate_reweights_by_target_classes():
    # reference: class 1 rate 0.1 (2000 px), class 2 rate 0.5 (2000 px). target: all class 2 -> 0.5, not the pooled 0.3
    cls = np.array([1] * 2000 + [2] * 2000 + [2] * 10)
    flag = np.array([1] * 200 + [0] * 1800 + [1] * 1000 + [0] * 1000 + [0] * 10, bool)
    ref = np.array([True] * 4000 + [False] * 10)
    r = change_rates.standardized_rate(flag, cls, ~ref, ref, min_n=1000)
    assert r["rate"] == pytest.approx(0.5)
    assert r["dropped_share"] == 0.0
    assert r["weights"] == {2: pytest.approx(1.0)}


def test_standardized_rate_drops_small_reference_classes():
    cls = np.array([1] * 2000 + [3] * 50 + [1] * 30 + [3] * 70)
    flag = np.zeros(cls.size, bool)
    flag[:1000] = True  # class 1 reference rate 0.5
    ref = np.zeros(cls.size, bool)
    ref[:2050] = True
    r = change_rates.standardized_rate(flag, cls, ~ref, ref, min_n=1000)  # target: 30 of class 1, 70 of class 3
    assert r["rate"] == pytest.approx(0.5)
    assert r["dropped_share"] == pytest.approx(0.7)
    assert r["dropped_classes"] == [3]


def test_components_8_connected():
    m = np.zeros((4, 4), bool)
    m[0, 0] = m[1, 1] = True  # diagonal: one component
    m[3, 3] = True
    lab = change_rates.components(m)
    assert lab[0, 0] == lab[1, 1] != lab[3, 3]
    assert lab[2, 0] == 0


def test_block_ids():
    b = change_rates.block_ids(np.array([0.0, 999.0, 1000.0, 2500.0]), np.array([0.0, 0.0, 0.0, 1500.0]), 1000)
    assert b[0] == b[1] != b[2]
    assert len(set(b)) == 3


def test_rate_draws_resample_whole_units():
    # 2 units: one all flagged, one never. Resampling units gives only 0, 0.5 or 1; resampling pixels would not
    flag = np.array([1] * 10 + [0] * 10, bool)
    units = np.array([0] * 10 + [1] * 10)
    d = change_rates.rate_draws(flag, units, 200, np.random.default_rng(0))
    assert set(np.round(d, 6)) <= {0.0, 0.5, 1.0}


def test_std_rate_draws_centre_on_the_point_value():
    rng = np.random.default_rng(4)
    units = np.repeat(np.arange(300), 40)
    cls = rng.choice([10, 50], size=units.size, p=[0.7, 0.3])
    flag = np.where(cls == 50, rng.random(units.size) < 0.2, rng.random(units.size) < 0.05)
    w = {10: 0.2, 50: 0.8}
    point = 0.2 * flag[cls == 10].mean() + 0.8 * flag[cls == 50].mean()
    d = change_rates.std_rate_draws(flag, cls, units, w, n=400, rng=np.random.default_rng(0))
    assert d.mean() == pytest.approx(point, abs=0.005)
    assert np.quantile(d, 0.05) < point < np.quantile(d, 0.95)


def write(path, a, dtype="float32", nodata=None):
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype=dtype,
                       crs="EPSG:32654", transform=from_origin(500000, 4000000, 10, 10), nodata=nodata) as dst:
        dst.write(a.astype(dtype), 1)


def test_cli_rates_against_a_standardised_control(tmp_path):
    # 40 x 40, 10 m pixels. Left half land cover 50 (built), right half 40 (cropland).
    # control (code 9): everything outside the group. built control: 5 % brighter; cropland control: 0 %.
    # group (code 1): rows 0-9, cols 0-9, all built, 30 of 100 pixels brighter, 10 darker.
    d = np.zeros((40, 40))
    cls = np.where(np.arange(40)[None, :] < 20, 50, 40) * np.ones((40, 1))
    grp = np.full((40, 40), 9)
    grp[:10, :10] = 1
    built_ctrl = np.argwhere((cls == 50) & (grp == 9))  # 800 - 100 = 700 pixels
    d[tuple(built_ctrl[:35].T)] = 4.0  # 35 / 700 = 0.05
    g = np.zeros(100)
    g[:30], g[30:40] = 4.0, -4.0
    d[:10, :10] = g.reshape(10, 10)
    d[39, 39] = np.nan  # one missing pixel, in the cropland control
    write(tmp_path / "d.tif", d, nodata=np.nan)
    write(tmp_path / "c.tif", cls, "uint8")
    write(tmp_path / "g.tif", grp, "uint8")
    out = subprocess.run([sys.executable, str(HERE / "change_rates.py"), "--delta", tmp_path / "d.tif",
                          "--groups", tmp_path / "g.tif", "--classes", tmp_path / "c.tif", "--control", "9",
                          "--block", "50", "--min-class", "100", "--n", "300"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["pixels"] == 1600 and r["missing"] == 1 and r["outside"] == 0
    assert r["groups"]["9"]["n"] == 1499
    g1 = r["groups"]["1"]
    assert g1["n"] == 100
    assert g1["brighter"]["rate"] == pytest.approx(0.30)
    assert g1["darker"]["rate"] == pytest.approx(0.10)
    # the group is all built, so the control rate is the built control rate, not the pooled 35 / 1499
    assert g1["brighter"]["control"] == pytest.approx(0.05)
    assert g1["brighter"]["ratio"] == pytest.approx(6.0)
    lo, hi = g1["brighter"]["ratio_90"]
    assert lo < 6.0 < hi
    assert g1["darker"]["control"] == 0.0
    assert g1["darker"]["ratio"] is None  # nothing to divide by: reported as null, not inf
    assert g1["control_dropped_share"] == 0.0


def test_cli_stops_on_unknown_control(tmp_path):
    a = np.zeros((4, 4))
    write(tmp_path / "d.tif", a, nodata=np.nan)
    write(tmp_path / "c.tif", a, "uint8")
    write(tmp_path / "g.tif", a + 1, "uint8")
    out = subprocess.run([sys.executable, str(HERE / "change_rates.py"), "--delta", tmp_path / "d.tif",
                          "--groups", tmp_path / "g.tif", "--classes", tmp_path / "c.tif", "--control", "9"],
                         capture_output=True, text=True)
    assert out.returncode != 0
    assert "control" in out.stderr
