"""Reading the GSI elevation tiles: tile and pixel numbers, and the elevation at a point.

DEM5A is layer `dem5a` at zoom 15, DEM10B is layer `dem` at zoom 14. A tile is 256 x 256 values in m, rows from north
to south; `e` is no value, and a tile with no land is a 404 (kept as a `.404` file next to the tiles).
"""
import math
from pathlib import Path

import numpy as np

LAYERS = {"dem5a": 15, "dem": 14}


def global_pixel(lon, lat, z):
    """Pixel coordinates over the whole zoom level (pixel centres at .5)."""
    n = 256 * 2 ** z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def metres_per_pixel(lat, z):
    return 2 * math.pi * 6378137 * math.cos(math.radians(lat)) / (256 * 2 ** z)


def tiles_around(lon, lat, z, radius_m):
    gx, gy = global_pixel(lon, lat, z)
    k = radius_m / metres_per_pixel(lat, z)
    return {(x, y) for x in range(int((gx - k) // 256), int((gx + k) // 256) + 1)
            for y in range(int((gy - k) // 256), int((gy + k) // 256) + 1)}


def parse_tile(text):
    rows = [line.split(",") for line in text.split()]
    return np.array([[np.nan if v == "e" else float(v) for v in r] for r in rows])


class Tiles:
    """Elevation from tiles saved as <root>/<layer>/<z>/<x>_<y>.txt; missing values are nan."""

    def __init__(self, root, layer):
        self.dir = Path(root) / layer / str(LAYERS[layer])
        self.z = LAYERS[layer]
        self.cache = {}

    def tile(self, x, y):
        if (x, y) not in self.cache:
            p = self.dir / f"{x}_{y}.txt"
            self.cache[(x, y)] = parse_tile(p.read_text()) if p.exists() else None
        return self.cache[(x, y)]

    def pixel(self, px, py):
        """Value of the pixel that contains global pixel coordinates (px, py)."""
        t = self.tile(int(px // 256), int(py // 256))
        return np.nan if t is None else t[int(py % 256), int(px % 256)]

    def bilinear(self, px, py):
        """Bilinear between the four pixel centres around (px, py); nan if any of them is missing."""
        x0, y0 = math.floor(px - 0.5), math.floor(py - 0.5)
        fx, fy = px - 0.5 - x0, py - 0.5 - y0
        v = [[self.pixel(x0 + i + 0.5, y0 + j + 0.5) for i in (0, 1)] for j in (0, 1)]
        return (v[0][0] * (1 - fx) * (1 - fy) + v[0][1] * fx * (1 - fy)
                + v[1][0] * (1 - fx) * fy + v[1][1] * fx * fy)

    def window(self, lon, lat, radius_m):
        """Square of pixels around a point: (array, metres per pixel, row and column of the point)."""
        gx, gy = global_pixel(lon, lat, self.z)
        m = metres_per_pixel(lat, self.z)
        k = int(math.ceil(radius_m / m))
        cx, cy = int(gx), int(gy)
        x0, y0 = cx - k, cy - k
        a = np.full((2 * k + 1, 2 * k + 1), np.nan)
        for tx in range(x0 // 256, (cx + k) // 256 + 1):
            for ty in range(y0 // 256, (cy + k) // 256 + 1):
                t = self.tile(tx, ty)
                if t is None:
                    continue
                c0, c1 = max(x0, tx * 256), min(cx + k + 1, tx * 256 + 256)
                r0, r1 = max(y0, ty * 256), min(cy + k + 1, ty * 256 + 256)
                a[r0 - y0:r1 - y0, c0 - x0:c1 - x0] = t[r0 - ty * 256:r1 - ty * 256, c0 - tx * 256:c1 - tx * 256]
        return a, m, k, k


def drain_to(a):
    """For each pixel, the flat index of the pixel where steepest descent (8 neighbours, diagonal drop divided by
    sqrt 2) stops. A pixel with no lower neighbour stops on itself; depressions are not filled. nan pixels stop on
    themselves and are never entered."""
    h, w = a.shape
    big = np.where(np.isnan(a), np.inf, a)
    pad = np.pad(big, 1, constant_values=np.inf)
    best = np.zeros((h, w))
    rec = np.arange(h * w).reshape(h, w)
    rows, cols = np.indices((h, w))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            nb = pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
            with np.errstate(invalid="ignore"):  # inf - inf at nan pixels; not finite, so never taken
                slope = (big - nb) / (math.sqrt(2) if dy and dx else 1.0)
            take = (slope > best) & np.isfinite(slope)
            best = np.where(take, slope, best)
            rec = np.where(take, (rows + dy) * w + (cols + dx), rec)
    r = rec.ravel()
    while True:
        nxt = r[r]
        if np.array_equal(nxt, r):
            return r.reshape(h, w)
        r = nxt
