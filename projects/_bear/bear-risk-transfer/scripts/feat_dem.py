"""Elevation and slope per 100 m cell from the GSI elevation tiles (zoom 12, text), by the centre of each pixel.

The tiles are fetched once into RAW_DIR (skipped if already there) with a pause between requests: it is a
public server. A pixel without a value (`e`, the sea) is NoData. Writes `dem.npz` with `elev` (mean of the
valid pixels in the cell, m; NaN where none) and `slope` (degrees, from the 100 m elevation grid), and the
count of valid pixels per cell (`n`).

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --with numpy --with pyproj \
        python feat_dem.py ART_DIR RAW_DIR
"""

import json
import math
import os
import sys
import time
import urllib.request

import numpy as np

import rasteragg as ra
from grid import Grid, load, lonlat_bbox, worldcover_tiles

URL = "https://cyberjapandata.gsi.go.jp/xyz/dem/{z}/{x}/{y}.txt"
Z = 12


def parse_tile(text, size=256):
    rows = [r for r in text.strip().split("\n") if r]
    a = np.array([[np.nan if v == "e" else float(v) for v in r.split(",")] for r in rows])
    if a.shape != (size, size):
        raise ValueError(f"tile shape {a.shape}, expected {(size, size)}")
    return a


def tile_pixel_centres(z, x, y, size=256):
    n = size * 2 ** z
    X = size * x + np.arange(size) + 0.5
    Y = size * y + np.arange(size) + 0.5
    lon = X / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * Y / n))))
    return np.meshgrid(lon, lat)


def tiles_for_bbox(minlon, minlat, maxlon, maxlat, z):
    n = 2 ** z

    def tx(lon):
        return int((lon + 180) / 360 * n)

    def ty(lat):
        return int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)

    return list(range(tx(minlon), tx(maxlon) + 1)), list(range(ty(maxlat), ty(minlat) + 1))


def fetch_tile(z, x, y, raw, pause=0.2):
    """Text of a tile, from RAW_DIR or the server. None for a tile the server does not have (404: no land).

    The 404 is remembered as an empty `.404` file. Any other HTTP error stops the run.
    """
    import urllib.error

    path, miss = f"{raw}/{z}_{x}_{y}.txt", f"{raw}/{z}_{x}_{y}.404"
    if os.path.exists(path):
        return open(path).read()
    if os.path.exists(miss):
        return None
    try:
        with urllib.request.urlopen(URL.format(z=z, x=x, y=y), timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        open(miss, "w").close()
        data = None
    finally:
        time.sleep(pause)
    if data is None:
        return None
    open(path, "wb").write(data)
    return data.decode()


def slope_deg(elev, spacing):
    gy, gx = np.gradient(elev, spacing)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def main():
    import pyproj

    art, raw = sys.argv[1], sys.argv[2]
    os.makedirs(raw, exist_ok=True)
    g, CRS = load(art)
    BBOX = lonlat_bbox(g, CRS)
    muni = np.load(f"{art}/grid_mask.npz")["muni"]
    tr = pyproj.Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    xs, ys = tiles_for_bbox(*BBOX, Z)
    print(f"z{Z}: {len(xs)} x {len(ys)} = {len(xs) * len(ys)} tiles")
    acc = ra.MeanAcc(g)
    missing = 0
    for x in xs:
        for y in ys:
            text = fetch_tile(Z, x, y, raw)
            if text is None:
                missing += 1
                continue
            a = parse_tile(text)
            lon, lat = tile_pixel_centres(Z, x, y)
            px, py = tr.transform(lon.ravel(), lat.ravel())
            acc.add(a.ravel(), px, py, nodata=None)
    print("tiles the server does not have (404, no land):", missing)
    inside = muni >= 0
    elev = acc.mean()
    print("pixels per cell in the prefecture (min, median, max):", int(acc.n[inside].min()), float(np.median(acc.n[inside])), int(acc.n[inside].max()))
    print("prefecture cells without a valid pixel (sea or lake edge):", int(np.isnan(elev[inside]).sum()))
    print("elevation in the prefecture (min, median, max, m):", float(np.nanmin(elev[inside])), float(np.nanmedian(elev[inside])), float(np.nanmax(elev[inside])))
    slope = slope_deg(elev, g.size)
    np.savez_compressed(f"{art}/dem.npz", elev=elev.astype(np.float32), slope=slope.astype(np.float32), n=acc.n.astype(np.int32))
    print("wrote dem.npz")


if __name__ == "__main__":
    main()
