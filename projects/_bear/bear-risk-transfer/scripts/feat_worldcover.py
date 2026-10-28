"""Land cover fractions per 100 m cell from ESA WorldCover 2021 (v200, 10 m), by the centre of each pixel.

Reads only the window of the Akita bounding box from the two 3 x 3 degree tiles, in row blocks. Each pixel
centre is moved to EPSG:6678 and counted in its cell (the raster itself is not resampled). Class 0 is
NoData (open sea). Writes `worldcover.npz` with the fraction of each class over the valid pixels of the cell
(`f10` tree cover, `f20` shrub, `f30` grass, `f40` cropland, `f50` built-up, `f60` bare, `f80` water,
`f90` wetland, ...) and the count of valid pixels (`valid`).

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --with rasterio --with numpy --with pyproj \
        python feat_worldcover.py ART_DIR
"""

import json
import sys
import time

import numpy as np

import rasteragg as ra
from grid import Grid, load, lonlat_bbox, worldcover_tiles

URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
CLASSES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]


def main():
    import pyproj
    import rasterio
    from rasterio.windows import from_bounds

    art = sys.argv[1]
    g, CRS = load(art)
    BBOX = lonlat_bbox(g, CRS)
    muni = np.load(f"{art}/grid_mask.npz")["muni"]
    tr = pyproj.Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    acc = ra.ClassAcc(g, CLASSES)
    t0 = time.time()
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        for tile in worldcover_tiles(BBOX):
            with rasterio.open(URL.format(tile=tile)) as src:
                print(tile, src.crs, src.res, src.nodata, src.width, src.height)
                win = from_bounds(*BBOX, transform=src.transform).round_offsets().round_lengths()
                win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
                r0, c0, nr, nc = int(win.row_off), int(win.col_off), int(win.height), int(win.width)
                print(f"  window rows {r0}..{r0 + nr}, cols {c0}..{c0 + nc}")
                for rr in range(r0, r0 + nr, 512):
                    h = min(512, r0 + nr - rr)
                    vals = src.read(1, window=rasterio.windows.Window(c0, rr, nc, h))
                    lon, lat = ra.pixel_centres(src.transform, rr, h, c0, nc)
                    x, y = tr.transform(lon.ravel(), lat.ravel())
                    acc.add(vals.ravel(), x, y, nodata=0)
                print(f"  done {time.time() - t0:.0f} s")
    inside = muni >= 0
    valid = acc.valid()
    print("pixels per cell in the prefecture (min, median, max):", int(valid[inside].min()), float(np.median(valid[inside])), int(valid[inside].max()))
    print("cells in the prefecture without a valid pixel:", int((valid[inside] == 0).sum()), "| NoData pixels in prefecture cells:", int(acc.nodata[inside].sum()))
    fr = acc.fractions()
    share = {c: float(np.nansum(acc.counts[c][inside]) / valid[inside].sum()) for c in CLASSES}
    print("class shares over the prefecture:", {c: round(v, 4) for c, v in share.items() if v > 0})
    other = int(acc.other[inside].sum())
    print("pixels of a class not in the legend:", other)
    np.savez_compressed(f"{art}/worldcover.npz", valid=valid.astype(np.int32),
                        **{f"f{c}": fr[c].astype(np.float32) for c in CLASSES})
    print("wrote worldcover.npz")


if __name__ == "__main__":
    main()
