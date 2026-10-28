"""People per 100 m cell from WorldPop R2025A, 2020, 100 m constrained (a quantity: summed, never averaged).

Each WorldPop pixel (3 arc-seconds, about 93 m x 71 m here) goes whole to the cell holding its centre, so a
cell gets one or two pixels and the per-cell values are blocky; the model uses sums over neighbourhoods
(built later), not the single cell. The total in the prefecture's cells is printed next to the 2020 census
population of the prefecture (jp-admin-2026-09). Writes `worldpop.npz` with `pop`.

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with rasterio \
        --with numpy --with pyproj python feat_worldpop.py ART_DIR
"""

import json
import sys

import numpy as np

import rasteragg as ra
from grid import CRS, Grid

URL = ("https://huggingface.co/datasets/yuiseki/worldpop-jp-2026-01/resolve/cb54e5985662c617a235278bc3529cc172e6368c/"
       "cog/GIS/Population/Global_2015_2030/R2025A/2020/JPN/v1/100m/constrained/jpn_pop_2020_CN_100m_R2025A_v1.tif")
PREF = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/prefectures.parquet"
BBOX = (139.60, 38.80, 141.10, 40.60)


def main():
    import duckdb
    import pyproj
    import rasterio
    from rasterio.windows import Window, from_bounds

    art = sys.argv[1]
    meta = json.load(open(f"{art}/grid.json"))
    g = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    muni = np.load(f"{art}/grid_mask.npz")["muni"]
    tr = pyproj.Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    acc = ra.SumAcc(g)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        with rasterio.open(URL) as src:
            print(src.crs, src.res, "nodata", src.nodata, src.dtypes)
            win = from_bounds(*BBOX, transform=src.transform).round_offsets().round_lengths()
            win = win.intersection(Window(0, 0, src.width, src.height))
            vals = src.read(1, window=win)
            lon, lat = ra.pixel_centres(src.transform, int(win.row_off), int(win.height), int(win.col_off), int(win.width))
    x, y = tr.transform(lon.ravel(), lat.ravel())
    acc.add(vals.ravel(), x, y, nodata=src.nodata)
    inside = muni >= 0
    valid = vals[vals != src.nodata]
    print(f"window total {valid.sum():,.0f}; in prefecture cells {acc.total[inside].sum():,.0f}; "
          f"in grid cells outside the prefecture {acc.total[~inside].sum():,.0f}; off the grid {acc.outside:,.0f}")
    census = duckdb.sql(f"SELECT population FROM '{PREF}' WHERE pref_code = '05'").fetchall()[0][0]
    print(f"2020 census population of Akita: {census:,}; WorldPop in prefecture cells / census = {acc.total[inside].sum() / census:.4f}")
    print("prefecture cells with people > 0:", int((acc.total[inside] > 0).sum()), "of", int(inside.sum()))
    np.savez_compressed(f"{art}/worldpop.npz", pop=acc.total.astype(np.float32))
    print("wrote worldpop.npz")


if __name__ == "__main__":
    main()
