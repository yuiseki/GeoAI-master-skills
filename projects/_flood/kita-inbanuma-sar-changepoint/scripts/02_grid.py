"""Stack the RTC series of each orbit on one grid, and put the other inputs on the same grid.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --from 'duckdb>=1.5.5' --with rasterio --with numpy --with scipy --with shapely --with pyproj python scripts/02_grid.py

Writes to artifacts/_flood/kita-inbanuma-sar-changepoint/:
- stack_o39.npy, stack_o141.npy: float32 linear gamma0, shape (2 [vv, vh], ndate, rows, cols); nan where missing (nodata or <= 0)
- aux.npz: transform, dates_o39, dates_o141 (YYYY-MM-DD), dem (DEM5A bilinear, DEM10B where missing), dem_src (1 5A, 2 10B, 0 none),
  wc (WorldCover 2021 class, nearest), ref_0922, ref_0924, ref_0925, ref_1001 (GSI outlines, pixel centre inside)
and outputs/grid_summary.json (grid, dates, missing counts, outline areas). Every RTC file of the box must be on the same
grid (same transform and shape); the script stops otherwise.
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
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/kita-inbanuma-sar-changepoint"
RAW = ART / "raw"
UTM = "EPSG:32654"
ORBITS = (39, 141)
VERSIONS = {"ref_0922": "2026-09-22", "ref_0924": "2026-09-24", "ref_0925": "2026-09-25", "ref_1001": "2026-10-01"}


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
    summary = {"orbits": {}}
    grid = None
    aux = {}
    for o in ORBITS:
        files = sorted((RAW / "rtc").glob(f"o{o}_*_vv.tif"))
        dates = [f.name.split("_")[1] for f in files]
        stack = None
        missing = []
        for t, f in enumerate(files):
            for k, pol in enumerate(("vv", "vh")):
                with rasterio.open(f.with_name(f.name.replace("_vv.", f"_{pol}."))) as src:
                    g = (tuple(src.transform)[:6], src.shape)
                    grid = grid or g
                    if g != grid:
                        raise RuntimeError(f"{f.name} {pol}: grid {g} differs from {grid}")
                    a = src.read(1).astype(np.float32)
                    bad = (a == src.nodata) | ~np.isfinite(a) | (a <= 0)
                    a[bad] = np.nan
                if stack is None:
                    stack = np.full((2, len(files)) + a.shape, np.nan, np.float32)
                stack[k, t] = a
                missing.append({"date": dates[t], "pol": pol, "missing": int(bad.sum())})
        np.save(ART / f"stack_o{o}.npy", stack)
        aux[f"dates_o{o}"] = np.array(dates)
        summary["orbits"][o] = {"dates": dates, "missing": missing}
        print("orbit", o, len(dates), "dates")

    transform = rasterio.Affine(*grid[0])
    shape = grid[1]
    lon, lat = centres_lonlat(transform, shape)
    d5 = dem_at("dem5a", 15, lon, lat)
    d10 = dem_at("dem", 14, lon, lat)
    aux["dem"] = np.where(np.isnan(d5), d10, d5).astype(np.float32)
    aux["dem_src"] = np.where(~np.isnan(d5), 1, np.where(~np.isnan(d10), 2, 0)).astype(np.uint8)

    wc = np.zeros(shape, np.uint8)
    with rasterio.open(RAW / "worldcover_2021.tif") as src:
        reproject(src.read(1), wc, src_transform=src.transform, src_crs=src.crs, dst_transform=transform,
                  dst_crs=UTM, resampling=Resampling.nearest)
    aux["wc"] = wc

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
        aux[key] = rasterize([g], out_shape=shape, transform=transform, all_touched=False).astype(bool)
        areas[key] = {"polygon_utm_km2": round(g.area / 1e6, 4), "painted_km2": round(aux[key].sum() * 100 / 1e6, 4)}

    np.savez_compressed(ART / "aux.npz", transform=np.array(grid[0]), **aux)
    summary.update({"grid": {"crs": UTM, "shape": list(shape), "transform": list(grid[0])},
                    "dem_source_pixels": {"dem5a": int((aux["dem_src"] == 1).sum()),
                                          "dem10b": int((aux["dem_src"] == 2).sum()),
                                          "none": int((aux["dem_src"] == 0).sum())},
                    "worldcover_classes": {int(k): int(v) for k, v in zip(*np.unique(wc, return_counts=True))},
                    "outlines": areas})
    (HERE.parent / "outputs").mkdir(exist_ok=True)
    (HERE.parent / "outputs/grid_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
                                                          encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "orbits"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
