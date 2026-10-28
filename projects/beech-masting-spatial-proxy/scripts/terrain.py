"""Terrain features of the 98 Tohoku Dryad beech sites from the frozen Mapterhorn copy (zoom 12, Terrarium WebP),
as fixed in EXPERIMENT_PLAN.md:

    elev_dem          DEM elevation at the site (bilinear), only to check Dryad's Altitude, which stays the feature
    slope             degrees, from a plane fitted to the DEM pixels within 100 m of the site
    northness         cos(aspect), aspect = azimuth of the downslope direction of that plane (0 if flat)
    eastness          sin(aspect)
    relief_300/1000   max - min of the DEM within 300 m / 1,000 m
    tpi_300/1000      elev_dem - mean of the DEM within 300 m / 1,000 m

Distances are measured in EPSG:6691 (JGD2011 / UTM zone 54N) after moving each Web Mercator pixel centre there.
Tiles are cached under ART/mapterhorn-z12/ with their sha256 in outputs/terrain_audit.json.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pmtiles --with pillow --with pyproj --with pandas --with numpy python \
      projects/beech-masting-spatial-proxy/scripts/terrain.py projects/beech-masting-spatial-proxy/outputs \
      artifacts/beech-masting-spatial-proxy
"""

import argparse
import hashlib
import io
import json
import math
import time
import urllib.request
from pathlib import Path

import numpy as np

PMTILES = "https://z.yuiseki.net/static/mapterhorn/2026-01-06/planet.pmtiles"
DRYAD = ("hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8"
         "/parquet/study_sites.parquet")
ZOOM = 12
TILE = 512
R_PLANE = 100.0
RADII = (300.0, 1000.0)
UA = "GeoAI-master-skills beech-masting-spatial-proxy (yuiseki)"


def decode_terrarium(rgb):
    """Terrarium RGB to metres: R * 256 + G + B / 256 - 32768."""
    rgb = np.asarray(rgb, dtype=np.float64)
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0


def global_pixel(lon, lat, z):
    """Web Mercator pixel coordinates (x right, y down) at zoom z for 512 px tiles."""
    n = TILE * 2 ** z
    x = (lon + 180.0) / 360.0 * n
    phi = math.radians(lat)
    y = (1.0 - math.log(math.tan(phi) + 1.0 / math.cos(phi)) / math.pi) / 2.0 * n
    return x, y


def lonlat_of_global_pixel(x, y, z):
    n = TILE * 2 ** z
    lon = np.asarray(x) / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1.0 - 2.0 * np.asarray(y) / n))))
    return lon, lat


def slope_aspect(x, y, z):
    """Plane z = a x + b y + c by least squares (x east, y north, metres). Returns (slope in degrees, northness,
    eastness). The aspect is the azimuth of the downslope direction (-a, -b); a flat plane gives (0, 0, 0)."""
    A = np.column_stack([x, y, np.ones_like(x)])
    (a, b, _), *_ = np.linalg.lstsq(A, z, rcond=None)
    g = math.hypot(a, b)
    if g < 1e-12:
        return 0.0, 0.0, 0.0
    return math.degrees(math.atan(g)), -b / g, -a / g


def relief_tpi(x, y, z, at, r):
    """Within r of the origin: max - min, and the value `at` minus the mean."""
    inside = np.hypot(x, y) <= r
    v = z[inside]
    return float(v.max() - v.min()), float(at - v.mean())


class Tiles:
    def __init__(self, cache):
        from pmtiles.reader import Reader

        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.reader = Reader(self._get_bytes)
        self.header = self.reader.header()
        self.hashes = {}

    @staticmethod
    def _get_bytes(offset, length, tries=3):
        """One Range read. A 200 (the whole 664 GB file) is closed unread and retried; after `tries` it stops."""
        req = urllib.request.Request(PMTILES, headers={"Range": f"bytes={offset}-{offset + length - 1}",
                                                       "User-Agent": UA})
        for k in range(tries):
            with urllib.request.urlopen(req, timeout=120) as r:
                if r.status == 206:
                    data = r.read()
                    if len(data) != length:
                        raise RuntimeError(f"short read: {len(data)} of {length} bytes")
                    return data
            time.sleep(2 * (k + 1))
        raise RuntimeError(f"no partial response after {tries} tries")

    def get(self, x, y):
        path = self.cache / f"{ZOOM}-{x}-{y}.webp"
        if not path.exists():
            data = self.reader.get(ZOOM, x, y)
            if data is None:
                raise RuntimeError(f"tile {ZOOM}/{x}/{y} is missing")
            path.write_bytes(data)
        data = path.read_bytes()
        self.hashes[f"{ZOOM}/{x}/{y}"] = hashlib.sha256(data).hexdigest()
        from PIL import Image

        img = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
        if img.shape != (TILE, TILE, 3):
            raise RuntimeError(f"tile {ZOOM}/{x}/{y} has shape {img.shape}")
        return decode_terrarium(img)


def window(tiles, px, py, half):
    """DEM pixels whose global pixel index is within `half` of (px, py): (ix, iy, z) as flat arrays."""
    x0, x1 = int(math.floor(px - half)), int(math.floor(px + half))
    y0, y1 = int(math.floor(py - half)), int(math.floor(py + half))
    ix, iy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    z = np.empty(ix.shape)
    for tx in range(x0 // TILE, x1 // TILE + 1):
        for ty in range(y0 // TILE, y1 // TILE + 1):
            t = tiles.get(tx, ty)
            m = (ix // TILE == tx) & (iy // TILE == ty)
            z[m] = t[iy[m] - ty * TILE, ix[m] - tx * TILE]
    return ix.ravel(), iy.ravel(), z.ravel()


def bilinear(ix, iy, z, px, py):
    """Value at global pixel position (px, py); pixel (i, j) has its centre at (i + 0.5, j + 0.5)."""
    lut = {(int(a), int(b)): v for a, b, v in zip(ix, iy, z)}
    fx, fy = px - 0.5, py - 0.5
    i, j = int(math.floor(fx)), int(math.floor(fy))
    dx, dy = fx - i, fy - j
    return ((1 - dx) * (1 - dy) * lut[(i, j)] + dx * (1 - dy) * lut[(i + 1, j)]
            + (1 - dx) * dy * lut[(i, j + 1)] + dx * dy * lut[(i + 1, j + 1)])


def site_features(tiles, to_utm, lon, lat):
    px, py = global_pixel(lon, lat, ZOOM)
    ground = 2 * math.pi * 6378137.0 * math.cos(math.radians(lat)) / (TILE * 2 ** ZOOM)
    ix, iy, z = window(tiles, px, py, max(RADII) / ground + 3)
    plon, plat = lonlat_of_global_pixel(ix + 0.5, iy + 0.5, ZOOM)
    ex, ny = to_utm.transform(plon, plat)
    sx, sy = to_utm.transform(lon, lat)
    x, y = np.asarray(ex) - sx, np.asarray(ny) - sy
    at = bilinear(ix, iy, z, px, py)
    near = np.hypot(x, y) <= R_PLANE
    s, northness, eastness = slope_aspect(x[near], y[near], z[near])
    out = {"elev_dem": at, "slope": s, "northness": northness, "eastness": eastness,
           "pixel_m": ground, "n_plane": int(near.sum())}
    for r in RADII:
        relief, tpi = relief_tpi(x, y, z, at, r)
        out[f"relief_{int(r)}"] = relief
        out[f"tpi_{int(r)}"] = tpi
        out[f"n_{int(r)}"] = int((np.hypot(x, y) <= r).sum())
        out[f"nonpositive_{int(r)}"] = int(((np.hypot(x, y) <= r) & (z <= 0)).sum())
    return out


def main():
    import duckdb
    import pandas as pd
    from pyproj import Transformer

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    a = ap.parse_args()
    con = duckdb.connect()
    con.sql("install httpfs; load httpfs")
    sites = con.sql(f"""select ID, Latitude lat, Longitude lon, Altitude alt from '{DRYAD}'
                        where Location = 'Tohoku region in Honshu' order by ID""").df()
    if len(sites) != 98 or sites.ID.min() != 5:
        raise ValueError(f"expected the 98 Tohoku sites (ID 5-102), got {len(sites)}")
    tiles = Tiles(a.art / "mapterhorn-z12")
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:6691", always_xy=True)
    rows = []
    for s in sites.itertuples():
        f = site_features(tiles, to_utm, s.lon, s.lat)
        rows.append({"ID": s.ID, "lat": s.lat, "lon": s.lon, "alt": s.alt, **f, "elev_diff": f["elev_dem"] - s.alt})
        print(s.ID, round(f["elev_dem"], 1), s.alt, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(a.outputs / "terrain_sites.csv", index=False, float_format="%.4f")
    d = df.elev_diff
    audit = {
        "pmtiles": PMTILES, "zoom": ZOOM, "header": {k: (v if isinstance(v, (int, float, str)) else str(v))
                                                    for k, v in tiles.header.items()},
        "tiles": dict(sorted(tiles.hashes.items())), "sites": len(df),
        "elev_diff_m": {"mean": float(d.mean()), "median": float(d.median()), "mae": float(d.abs().mean()),
                        "q05": float(d.quantile(0.05)), "q95": float(d.quantile(0.95)),
                        "corr": float(np.corrcoef(df.elev_dem, df.alt)[0, 1])},
        "abs_diff_over_100m": df.loc[d.abs() > 100, ["ID", "alt", "elev_dem", "elev_diff"]].round(1).to_dict("records"),
        "pixel_m": [float(df.pixel_m.min()), float(df.pixel_m.max())],
        "pixels_in_radius": {c: [int(df[c].min()), int(df[c].max())] for c in ["n_plane", "n_300", "n_1000"]},
        "nonpositive_pixels": int(df.nonpositive_300.sum() + df.nonpositive_1000.sum()),
    }
    (a.outputs / "terrain_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k != "tiles"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
