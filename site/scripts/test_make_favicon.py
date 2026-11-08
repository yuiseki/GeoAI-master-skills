"""uvx --python 3.12 --with shapely --with pillow --with numpy --with pytest pytest -q test_make_favicon.py"""

# Tests for make-favicon.py: a 32x32 pixel globe with "GeoAI" on it, written as SVG and PNG.
# The script loads Natural Earth land when it is imported, from a cache file in /tmp or the network, and checks
# its sha256. Here the cache file is faked with a synthetic GeoJSON (Path.exists / Path.read_bytes for that one
# path), so nothing is downloaded or written outside tmp_path. main() writes into SITE/public, which is pointed
# at tmp_path.

import hashlib
import importlib.util
import json
import pathlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SRC = Path(__file__).parent / "make-favicon.py"
CACHE = "/tmp/geoai-site-cache/ne_110m_land.geojson"
WORLD = {"type": "Polygon", "coordinates": [[[-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]]]}


def geojson(*geoms):
    return json.dumps({"type": "FeatureCollection",
                       "features": [{"type": "Feature", "properties": {}, "geometry": g} for g in geoms]}).encode()


def load(monkeypatch, data: bytes, trust_hash=True):
    real_exists, real_read = pathlib.Path.exists, pathlib.Path.read_bytes
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: True if str(self) == CACHE else real_exists(self))
    monkeypatch.setattr(pathlib.Path, "read_bytes", lambda self: data if str(self) == CACHE else real_read(self))
    if trust_hash:
        class Pinned:
            def __init__(self, b):
                pass

            def hexdigest(self):
                return "9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9"

        monkeypatch.setattr(hashlib, "sha256", Pinned)
    spec = importlib.util.spec_from_file_location("make_favicon", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.undo()
    return mod


@pytest.fixture
def sea(monkeypatch):
    return load(monkeypatch, geojson())


@pytest.fixture
def land(monkeypatch):
    return load(monkeypatch, geojson(WORLD))


def test_a_cache_file_that_does_not_match_the_pinned_hash_stops_the_script(monkeypatch):
    with pytest.raises(SystemExit, match="pinned sha256"):
        load(monkeypatch, geojson(WORLD), trust_hash=False)


def test_the_globe_is_an_opaque_disc_on_a_transparent_square(sea):
    rgba = sea.globe()
    assert rgba.shape == (32, 32, 4) and rgba.dtype == np.uint8
    alpha = rgba[..., 3]
    assert set(np.unique(alpha)) == {0, 255}
    assert alpha[0, 0] == alpha[0, 31] == alpha[31, 0] == alpha[31, 31] == 0
    assert alpha[16, 16] == 255
    # a disc of radius 15.2 pixels covers pi * 15.2^2 = 726 pixels, give or take its jagged edge
    assert abs(int((alpha == 255).sum()) - 726) <= 20
    # the disc is centred: the alpha mask is the same mirrored either way
    assert np.array_equal(alpha, alpha[::-1, :]) and np.array_equal(alpha, alpha[:, ::-1])


def test_the_globe_is_the_same_on_every_run(sea):
    # clouds come from fixed waves, not random noise
    assert np.array_equal(sea.globe(), sea.globe())


def test_with_no_land_the_disc_is_ocean_blue(sea):
    rgba = sea.globe()
    opaque = rgba[..., 3] == 255
    clear = opaque & (np.abs(rgba[..., :3].astype(int) - sea.CLOUD).sum(axis=-1) > 150)   # not under cloud
    assert clear.sum() > 300
    assert (rgba[clear][:, 2] > rgba[clear][:, 0]).all()


def test_with_land_everywhere_the_disc_is_not_ocean(land, sea):
    a, b = land.globe(), sea.globe()
    opaque = a[..., 3] == 255
    assert np.array_equal(opaque, b[..., 3] == 255)
    # land changes the colour of uncovered pixels, and land at mid latitudes has more red than blue
    assert (a[..., :3] != b[..., :3]).any(axis=-1)[opaque].mean() > 0.5
    assert a[16, 16, 0] > a[16, 16, 2]


def test_the_specular_highlight(sea):
    assert (sea.globe()[8, 9, :3] >= 200).all()


def test_the_word_is_42_ink_pixels_centred_in_rows_13_to_17(sea):
    rgba = np.zeros((32, 32, 4), dtype=np.uint8)
    sea.draw_text(rgba)
    ink = np.argwhere((rgba == sea.TEXT).all(axis=-1))
    # G 9 + e 8 + o 6 + A 10 + I 9; five 3-wide glyphs with 1 pixel gaps = 19 wide, from column (32 - 19) // 2 = 6
    assert len(ink) == 42
    assert ink[:, 0].min() == 13 and ink[:, 0].max() == 17
    assert ink[:, 1].min() == 6 and ink[:, 1].max() == 24
    outline = np.argwhere((rgba == sea.OUTLINE).all(axis=-1))
    assert outline[:, 0].min() == 12 and outline[:, 0].max() == 18
    assert outline[:, 1].min() == 5 and outline[:, 1].max() == 25
    # nothing else is touched
    assert int((rgba[..., 3] > 0).sum()) == len(ink) + len(outline)


def test_svg_merges_runs_of_one_colour_and_skips_transparent_pixels(sea):
    rgba = np.zeros((32, 32, 4), dtype=np.uint8)
    rgba[0, 2:5] = (255, 0, 16, 255)
    rgba[0, 5] = (0, 1, 2, 255)
    rgba[3, 31] = (10, 20, 30, 255)
    svg = sea.to_svg(rgba)
    assert svg == ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" shape-rendering="crispEdges">'
                   '<rect x="2" y="0" width="3" height="1" fill="#ff0010"/>'
                   '<rect x="5" y="0" width="1" height="1" fill="#000102"/>'
                   '<rect x="31" y="3" width="1" height="1" fill="#0a141e"/>'
                   '</svg>\n')


def test_scaling_is_by_whole_pixels(sea):
    rgba = np.zeros((32, 32, 4), dtype=np.uint8)
    rgba[1, 2] = (9, 8, 7, 255)
    img = np.array(sea.scaled(rgba, 5))
    assert img.shape == (160, 160, 4)
    assert (img[5:10, 10:15] == (9, 8, 7, 255)).all()
    assert (img[4, 10:15] == 0).all() and (img[5:10, 15] == 0).all()


def test_main_writes_the_three_icons(sea, tmp_path, monkeypatch, capsys):
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(sea, "SITE", tmp_path)
    sea.main()
    pub = tmp_path / "public"
    svg = (pub / "favicon.svg").read_text(encoding="utf-8")
    assert svg.startswith("<svg ") and svg.count("<rect ") > 100
    with Image.open(pub / "favicon-32.png") as im:
        assert (im.size, im.mode) == ((32, 32), "RGBA")
    with Image.open(pub / "apple-touch-icon.png") as im:
        # iOS paints transparency black, so the touch icon is opaque with the page colour around the globe
        assert (im.size, im.mode) == ((180, 180), "RGB")
        assert im.getpixel((0, 0)) == (245, 248, 248)
    out = capsys.readouterr().out
    for name in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        assert f"{name} {(pub / name).stat().st_size} bytes" in out
