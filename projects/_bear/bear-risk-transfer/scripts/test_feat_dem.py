import math

import numpy as np

import feat_dem as fd


def test_parse_tile_reads_numbers_and_e_as_nan():
    text = "1.5,e\n2.25,3\n"
    a = fd.parse_tile(text, size=2)
    assert a[0, 0] == 1.5 and np.isnan(a[0, 1]) and a[1, 1] == 3.0


def test_parse_tile_stops_on_a_wrong_shape():
    try:
        fd.parse_tile("1,2\n3,4\n", size=3)
        raise AssertionError("should stop")
    except ValueError:
        pass


def test_tile_pixel_centres_match_web_mercator():
    lon, lat = fd.tile_pixel_centres(0, 0, 0, size=256)
    # pixel (0, 0) of the single z0 tile: X = 0.5 of 256
    assert math.isclose(lon[0, 0], 0.5 / 256 * 360 - 180)
    assert math.isclose(lat[0, 0], math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * 0.5 / 256)))))
    # the middle row boundary is the equator: rows 127 and 128 are symmetric
    assert math.isclose(lat[127, 0], -lat[128, 0])


def test_tiles_for_bbox_cover_the_corners():
    xs, ys = fd.tiles_for_bbox(139.69, 38.87, 141.0, 40.52, 12)
    assert xs[0] == 3637 and xs[-1] == 3652 and ys[0] == 1542 and ys[-1] == 1567


def test_slope_of_a_plane():
    # elevation rises 10 m per 100 m eastward: slope atan(0.1)
    elev = np.tile(np.arange(5) * 10.0, (4, 1))
    s = fd.slope_deg(elev, 100.0)
    assert np.allclose(s[1:-1, 1:-1], math.degrees(math.atan(0.1)))


def test_fetch_treats_404_as_a_tile_without_values_and_remembers_it(tmp_path, monkeypatch):
    import urllib.error

    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(fd.urllib.request, "urlopen", fake_urlopen)
    assert fd.fetch_tile(12, 1, 2, str(tmp_path), pause=0) is None
    assert fd.fetch_tile(12, 1, 2, str(tmp_path), pause=0) is None
    assert len(calls) == 1  # the 404 is remembered on disk, not asked again


def test_fetch_stops_on_other_http_errors(tmp_path, monkeypatch):
    import urllib.error

    def fake_urlopen(url, timeout):
        raise urllib.error.HTTPError(url, 503, "Unavailable", None, None)

    monkeypatch.setattr(fd.urllib.request, "urlopen", fake_urlopen)
    try:
        fd.fetch_tile(12, 1, 2, str(tmp_path), pause=0)
        raise AssertionError("should stop")
    except urllib.error.HTTPError:
        pass
