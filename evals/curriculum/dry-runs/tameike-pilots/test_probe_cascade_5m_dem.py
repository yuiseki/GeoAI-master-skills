"""uvx --python 3.12 --with numpy --with scipy --with pytest pytest -q test_probe_cascade_5m_dem.py"""

# Tests for probe_cascade_5m_dem.py: web-mercator pixel maths, reading a GSI elevation text tile, and the
# JSON the probe writes. Tile downloads are replaced by synthetic tiles; nothing goes to the network, and the
# probe writes its JSON into tmp_path, not next to the script.

import importlib.util
import io
import json
import math
import urllib.error
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).parent / "probe_cascade_5m_dem.py"


@pytest.fixture
def probe(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("probe_cascade_5m_dem", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "OUTPUT_JSON", tmp_path / "out.json")
    return mod


# --- pixel maths ---------------------------------------------------------------------------------------

def test_the_origin_is_the_centre_of_the_world_tile(probe):
    assert probe.lonlat_to_global_pixel(0, 0, 0) == pytest.approx((128, 128))
    assert probe.lonlat_to_global_pixel(-180, 0, 0)[0] == pytest.approx(0)
    assert probe.lonlat_to_global_pixel(180, 0, 0)[0] == pytest.approx(256)


def test_the_mercator_limit_is_the_top_edge(probe):
    # 85.0511 degrees is where web mercator y reaches the edge of the square world
    assert probe.lonlat_to_global_pixel(0, 85.05112878, 0)[1] == pytest.approx(0, abs=1e-6)
    assert probe.lonlat_to_global_pixel(0, -85.05112878, 0)[1] == pytest.approx(256, abs=1e-6)


def test_each_zoom_doubles_the_pixel_coordinates(probe):
    x1, y1 = probe.lonlat_to_global_pixel(134.8, 34.45, 14)
    x2, y2 = probe.lonlat_to_global_pixel(134.8, 34.45, 15)
    assert (x2, y2) == pytest.approx((2 * x1, 2 * y1))


def test_metres_per_pixel(probe):
    # equator, zoom 0: the 40,075 km circumference over 256 pixels
    assert probe.metres_per_pixel(0, 0) == pytest.approx(2 * math.pi * 6378137 / 256)
    assert probe.metres_per_pixel(0, 0) == pytest.approx(156543.03, abs=0.01)
    # zoom 15 at 60 degrees: 2^15 times smaller and halved by cos 60
    assert probe.metres_per_pixel(60, 15) == pytest.approx(156543.03 / 2 ** 15 / 2, rel=1e-6)


def test_the_two_profile_ends_fall_in_the_same_z15_tile(probe):
    # main() reads the profile out of the upper pond's tile only, so both ends must be in it
    a = probe.lonlat_to_global_pixel(134.81725, 34.45350, 15)
    b = probe.lonlat_to_global_pixel(134.81719, 34.45433, 15)
    assert [int(v // 256) for v in a] == [int(v // 256) for v in b]


# --- fetching one tile ---------------------------------------------------------------------------------

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_a_tile_is_parsed_with_e_as_nan(probe, monkeypatch):
    seen = {}

    def urlopen(req, timeout):
        seen["url"], seen["timeout"] = req.full_url, timeout
        return FakeResponse(b"12.5,e,3\n4,5,-1.25\n")

    monkeypatch.setattr(probe.urllib.request, "urlopen", urlopen)
    code, arr = probe.fetch_gsi_tile("dem5a", 15, 28655, 13039)
    assert seen["url"] == "https://cyberjapandata.gsi.go.jp/xyz/dem5a/15/28655/13039.txt"
    assert code == 200
    assert arr.shape == (2, 3)
    assert np.isnan(arr[0, 1])
    assert arr[0, 0] == 12.5 and arr[1, 2] == -1.25


def test_an_http_error_returns_its_status_and_no_array(probe, monkeypatch):
    def urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(probe.urllib.request, "urlopen", urlopen)
    assert probe.fetch_gsi_tile("dem5a", 15, 0, 0) == (404, None)


def test_a_network_error_returns_its_message_and_no_array(probe, monkeypatch):
    def urlopen(req, timeout):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(probe.urllib.request, "urlopen", urlopen)
    code, arr = probe.fetch_gsi_tile("dem5a", 15, 0, 0)
    assert "no route" in code and arr is None


# --- main ----------------------------------------------------------------------------------------------

def synthetic_tile():
    """elevation = 1000 * row + column, so a sample says where it was read; two NaN ponds of 9 and 4 pixels."""
    rows, cols = np.mgrid[0:256, 0:256]
    arr = (1000 * rows + cols).astype(float)
    arr[10:13, 10:13] = np.nan
    arr[100:102, 50:52] = np.nan
    arr[200, 92] = np.nan   # one NaN pixel on the profile line
    return arr


def run_main(probe, monkeypatch, tile, status=200):
    calls = []

    def fetch(layer, z, x, y):
        calls.append((layer, z, x, y))
        return status, (tile.copy() if tile is not None else None)

    monkeypatch.setattr(probe, "fetch_gsi_tile", fetch)
    probe.main()
    return calls


def test_main_checks_three_layers_for_each_of_six_ponds(probe, monkeypatch):
    calls = run_main(probe, monkeypatch, synthetic_tile())
    out = json.loads(probe.OUTPUT_JSON.read_text(encoding="utf-8"))
    assert len(out["dem_comparison"]) == 6
    for layers in out["dem_comparison"].values():
        assert sorted(layers) == ["dem5a_z15", "dem5b_z15", "dem_z14"]
        assert all(v["status"] == 200 for v in layers.values())
        # 65,536 pixels, 9 + 4 + 1 NaN
        assert all(v["valid_pct"] == round((65536 - 14) / 65536 * 100, 2) for v in layers.values())
    # the z14 tile is the z15 tile index halved
    mannou = out["dem_comparison"]["香川県 まんのう町 満濃池"]
    assert (mannou["dem_z14"]["tile_x"], mannou["dem_z14"]["tile_y"]) == (
        mannou["dem5a_z15"]["tile_x"] // 2, mannou["dem5a_z15"]["tile_y"] // 2)
    assert ("dem", 14, 28655 // 2, 13039 // 2) in calls


def test_the_profile_reads_the_tile_along_the_line_between_the_ponds(probe, monkeypatch):
    run_main(probe, monkeypatch, synthetic_tile())
    prof = json.loads(probe.OUTPUT_JSON.read_text(encoding="utf-8"))["cascade_profiles"][0]
    samples = prof["profile"]
    # pixel (93, 219) to (92, 196): 23.02 pixels, so steps 0..23
    assert len(samples) == 24
    assert (samples[0]["px"], samples[0]["py"]) == (93, 219)
    assert (samples[-1]["px"], samples[-1]["py"]) == (92, 196)
    m = probe.metres_per_pixel(34.4535, 15)
    assert prof["pixel_resolution_m"] == round(m, 2)
    assert prof["total_distance_m"] == round(math.hypot(1, 23) * m, 1)
    for s in samples:
        if (s["px"], s["py"]) == (92, 200):
            assert s["elev_5m_m"] is None
        else:
            assert s["elev_5m_m"] == 1000 * s["py"] + s["px"]
    assert any(s["elev_5m_m"] is None for s in samples)


def test_nan_ponds_are_counted_as_connected_clusters(probe, monkeypatch):
    run_main(probe, monkeypatch, synthetic_tile())
    audit = json.loads(probe.OUTPUT_JSON.read_text(encoding="utf-8"))["nan_masking_audit"]
    assert audit["tile"] == "28655_13039"
    assert audit["nan_pixels"] == 14
    assert audit["n_waterbody_clusters"] == 3
    assert audit["top_cluster_sizes_pixels"] == [9, 4, 1]
    m2 = probe.metres_per_pixel(34.4535, 15) ** 2
    assert audit["top_cluster_areas_m2"] == [round(9 * m2, 1), round(4 * m2, 1), round(1 * m2, 1)]


def test_a_missing_5m_tile_stops_the_probe_without_writing_json(probe, monkeypatch):
    with pytest.raises(TypeError):
        run_main(probe, monkeypatch, None, status=404)
    assert not probe.OUTPUT_JSON.exists()
