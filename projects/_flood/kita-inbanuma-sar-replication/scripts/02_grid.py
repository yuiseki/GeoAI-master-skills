"""Put every input of stage A on the analysis grid (the RTC grid, EPSG:32654, 10 m, cut to the 27 x 17 km box).

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --from 'duckdb>=1.5.5' --with rasterio --with numpy --with scipy --with shapely --with pyproj python scripts/02_grid.py

Writes artifacts/_flood/kita-inbanuma-sar-replication/grid.npz (arrays below, and the grid transform) and
outputs/grid_summary.json (the counts of missing values and of filled pixels, and the painted outline areas).

- vv_b, vh_b, vv_a, vh_a: RTC gamma0 in dB, before (2026-09-12) and after (2026-09-24); nan where missing
- dem: DEM5A bilinear at pixel centres, filled from DEM10B where DEM5A is missing; dem_src 1 (5A), 2 (10B), 0 (none)
- water: WorldCover 2021 class 80 (permanent water bodies), nearest
- ref_0922, ref_0924, ref_0925, ref_1001: the GSI outlines, a pixel is in when its centre is inside
"""
import json
import math
from pathlib import Path

import duckdb
import numpy as np
import rasterio
import shapely
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds
from scipy import ndimage

from sar import to_db

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/kita-inbanuma-sar-replication"
RAW = ART / "raw"
CENTRE = (140.2582, 35.8063)
HALF = (13500, 8500)
UTM = "EPSG:32654"
VERSIONS = {"ref_0922": "2026-09-22", "ref_0924": "2026-09-24", "ref_0925": "2026-09-25", "ref_1001": "2026-10-01"}


def analysis_window():
    x, y = Transformer.from_crs("EPSG:4326", UTM, always_xy=True).transform(*CENTRE)
    with rasterio.open(RAW / "rtc_after_vv.tif") as src:
        w = from_bounds(x - HALF[0], y - HALF[1], x + HALF[0], y + HALF[1], transform=src.transform)
        w = w.round_offsets().round_lengths()
        return w, src.window_transform(w), (int(w.height), int(w.width))


def read_rtc(name, w):
    with rasterio.open(RAW / f"rtc_{name}.tif") as src:
        a = src.read(1, window=w).astype(float)
        a[a == src.nodata] = np.nan
    return to_db(a)


def centres_lonlat(transform, shape):
    rows, cols = np.mgrid[0:shape[0], 0:shape[1]]
    x = transform.c + (cols + 0.5) * transform.a
    y = transform.f + (rows + 0.5) * transform.e
    lon, lat = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True).transform(x, y)
    return np.asarray(lon), np.asarray(lat)


def dem_at(layer, z, lon, lat):
    """Bilinear elevation from the saved tiles at pixel centres; nan if any of the four values is missing."""
    d = RAW / layer / str(z)
    n = 256 * 2 ** z
    gx = (lon + 180) / 360 * n - 0.5
    gy = (1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * n - 0.5
    tx0, ty0 = int(gx.min() // 256) - 1, int(gy.min() // 256) - 1
    tx1, ty1 = int(gx.max() // 256) + 1, int(gy.max() // 256) + 1
    mosaic = np.full(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), np.nan)
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            p = d / f"{tx}_{ty}.txt"
            if p.exists():
                rows = [r.split(",") for r in p.read_text(encoding="utf-8").split()]
                mosaic[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = \
                    [[np.nan if v == "e" else float(v) for v in r] for r in rows]
    return ndimage.map_coordinates(mosaic, [gy - ty0 * 256, gx - tx0 * 256], order=1, mode="constant", cval=np.nan)


def main():
    w, transform, shape = analysis_window()
    out = {}
    for role, tag in (("before", "b"), ("after", "a")):
        for pol in ("vv", "vh"):
            out[f"{pol}_{tag}"] = read_rtc(f"{role}_{pol}", w)

    lon, lat = centres_lonlat(transform, shape)
    d5 = dem_at("dem5a", 15, lon, lat)
    d10 = dem_at("dem", 14, lon, lat)
    out["dem"] = np.where(np.isnan(d5), d10, d5)
    out["dem_src"] = np.where(~np.isnan(d5), 1, np.where(~np.isnan(d10), 2, 0)).astype(np.uint8)

    wc = np.zeros(shape, np.uint8)
    with rasterio.open(RAW / "worldcover_2021.tif") as src:
        reproject(src.read(1), wc, src_transform=src.transform, src_crs=src.crs, dst_transform=transform,
                  dst_crs=UTM, resampling=Resampling.nearest)
    out["water"] = wc == 80

    con = duckdb.connect()
    con.execute("load spatial")
    rows = con.sql(f"select strftime(version_time, '%Y-%m-%d') d, st_aswkb(geometry) from "
                   f"'{RAW / 'inundation_kita_inbanuma.parquet'}' order by version_time").fetchall()
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    areas = {}
    for key, day in VERSIONS.items():
        wkb = [r[1] for r in rows if r[0] == day]
        assert len(wkb) == 1, day
        g = shapely.transform(shapely.from_wkb(bytes(wkb[0])), lambda c: np.column_stack(to_utm.transform(c[:, 0], c[:, 1])))
        out[key] = rasterize([g], out_shape=shape, transform=transform, all_touched=False).astype(bool)
        areas[key] = {"polygon_utm_km2": round(g.area / 1e6, 4), "painted_km2": round(out[key].sum() * 100 / 1e6, 4)}

    np.savez_compressed(ART / "grid.npz", transform=np.array(transform)[:6], **out)
    summary = {"grid": {"crs": UTM, "shape": list(shape), "transform": list(transform)[:6],
                        "window_col_row": [int(w.col_off), int(w.row_off)]},
               "missing": {k: int(np.isnan(out[k]).sum()) for k in ("vv_b", "vh_b", "vv_a", "vh_a", "dem")},
               "dem_source_pixels": {"dem5a": int((out["dem_src"] == 1).sum()), "dem10b": int((out["dem_src"] == 2).sum()),
                                     "none": int((out["dem_src"] == 0).sum())},
               "worldcover_classes": {int(k): int(v) for k, v in zip(*np.unique(wc, return_counts=True))},
               "water_pixels": int(out["water"].sum()), "outlines": areas}
    (HERE.parent / "outputs/grid_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
