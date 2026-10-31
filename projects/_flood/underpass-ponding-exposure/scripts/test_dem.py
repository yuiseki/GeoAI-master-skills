import math

import numpy as np

from dem import Tiles, global_pixel, metres_per_pixel, parse_tile, tiles_around


def test_global_pixel_of_tile_corner():
    # the north-west corner of tile (0, 0) at any zoom is (-180, 85.0511)
    gx, gy = global_pixel(-180, 85.05112878, 3)
    assert abs(gx) < 1e-9 and abs(gy) < 1e-3


def test_metres_per_pixel_at_equator_z0():
    assert abs(metres_per_pixel(0, 0) - 156543.03) < 0.01


def test_tiles_around_contains_own_tile():
    gx, gy = global_pixel(139.77, 35.68, 15)
    assert (int(gx // 256), int(gy // 256)) in tiles_around(139.77, 35.68, 15, 10)


def test_parse_tile_reads_e_as_nan():
    a = parse_tile("1.00,e\n2.50,3.00\n")
    assert a.shape == (2, 2) and math.isnan(a[0, 1]) and a[1, 0] == 2.5


def _write(tmp_path, x, y, arr):
    d = tmp_path / "dem5a" / "15"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{x}_{y}.txt").write_text("\n".join(",".join(f"{v:.2f}" for v in r) for r in arr) + "\n")


def test_pixel_and_bilinear(tmp_path):
    arr = np.add.outer(np.arange(256) * 10.0, np.arange(256) * 1.0)  # value = 10 * row + col
    _write(tmp_path, 5, 7, arr)
    t = Tiles(tmp_path, "dem5a")
    assert t.pixel(5 * 256 + 3.2, 7 * 256 + 4.9) == 43.0
    # halfway between pixel centres of columns 3 and 4 in row 4
    assert abs(t.bilinear(5 * 256 + 4.0, 7 * 256 + 4.5) - 43.5) < 1e-9
    # a neighbour tile that does not exist gives nan
    assert math.isnan(t.pixel(6 * 256 + 1, 7 * 256 + 1))


def test_window_is_centred(tmp_path):
    arr = np.add.outer(np.arange(256) * 10.0, np.arange(256) * 1.0)
    _write(tmp_path, 0, 0, arr)
    t = Tiles(tmp_path, "dem5a")
    z = 15
    n = 256 * 2 ** z
    lon = (100.5) / n * 360 - 180  # pixel column 100
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * 50.5 / n))))  # pixel row 50
    a, m, r, c = t.window(lon, lat, 3 * metres_per_pixel(lat, z))
    assert a[r, c] == 10 * 50 + 100


def test_window_matches_pixel_across_tiles(tmp_path):
    rng = np.random.default_rng(0)
    for x in (0, 1):
        for y in (0, 1):
            _write(tmp_path, x, y, rng.uniform(0, 100, (256, 256)).round(2))
    t = Tiles(tmp_path, "dem5a")
    n = 256 * 2 ** 15
    lon = 255.5 / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * 255.5 / n))))
    a, m, r, c = t.window(lon, lat, 5 * metres_per_pixel(lat, 15))
    for j in range(a.shape[0]):
        for i in range(a.shape[1]):
            want = t.pixel(255 - r + i + 0.5, 255 - c + j + 0.5)
            assert (math.isnan(want) and math.isnan(a[j, i])) or a[j, i] == want


def test_drain_to_two_basins():
    from dem import drain_to
    # a ridge in column 2 splits two valleys with pits at (2, 0) and (2, 4)
    a = np.array([[5, 4, 6, 4, 5],
                  [4, 2, 7, 2, 4],
                  [3, 1, 8, 1, 3],
                  [4, 2, 7, 2, 4],
                  [5, 4, 6, 4, 5]], float)
    a[2, 0], a[2, 4] = 0, 0
    d = drain_to(a)
    assert d[0, 0] == 2 * 5 + 0 and d[4, 4] == 2 * 5 + 4
    assert d[2, 2] in (2 * 5 + 0, 2 * 5 + 4)
    assert (d == 10).sum() + (d == 14).sum() == 25


def test_drain_to_nan_is_not_entered():
    from dem import drain_to
    a = np.array([[3, 2, np.nan]], float)
    d = drain_to(a)
    assert d[0, 0] == 1 and d[0, 1] == 1 and d[0, 2] == 2


def test_terrarium_decode():
    from dem import terrarium
    rgb = np.zeros((1, 2, 3), np.uint8)
    rgb[0, 0] = (128, 0, 0)        # 0 m
    rgb[0, 1] = (128, 25, 64)      # 25.25 m
    v = terrarium(rgb)
    assert v[0, 0] == 0.0 and v[0, 1] == 25.25


def test_mapterhorn_tiles_512(tmp_path):
    from PIL import Image
    from dem import Tiles, terrarium_encode
    arr = np.add.outer(np.arange(512) * 1.0, np.arange(512) * 0.25)  # value = row + col / 4
    d = tmp_path / "mt" / "16"
    d.mkdir(parents=True)
    Image.fromarray(terrarium_encode(arr)).save(d / "3_5.webp", lossless=True)
    t = Tiles(tmp_path, "mt")
    assert t.size == 512 and t.z == 16
    assert t.pixel(3 * 512 + 10.5, 5 * 512 + 7.5) == 7 + 10 * 0.25
    lon = (3 * 512 + 100.5) / (512 * 2 ** 16) * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (5 * 512 + 50.5) / (512 * 2 ** 16)))))
    a, m, r, c = t.window(lon, lat, 3 * metres_per_pixel(lat, 16, 512))
    assert a[r, c] == 50 + 100 * 0.25
