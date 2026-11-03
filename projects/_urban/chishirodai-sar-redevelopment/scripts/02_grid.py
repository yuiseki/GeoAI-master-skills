"""Stack the orbit 46 RTC series on one grid and put the other inputs on it.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with scipy --with shapely --with pyproj --with scikit-image python scripts/02_grid.py

Writes to artifacts/_urban/chishirodai-sar-redevelopment/:
- stack.npy: float32 linear gamma0, shape (2 [vv, vh], ndate, rows, cols); nan where missing (nodata or <= 0). Only the
  dates from 2017-02-01 (dual polarisation). Where a date has two items they are merged (the first valid value wins);
  every item must be on the same grid (same transform and shape), the script stops otherwise.
- aux.npz: transform, dates, platforms, wc (WorldCover 2021 class, nearest), tile_x, tile_y (z16 tile of the pixel centre),
  site (pixel centre inside labels/site.geojson), ctrl (the CTRL set of EXPERIMENT_PLAN.md), dist_site (m)
and outputs/grid_summary.json (grid, dates per year, missing counts, set sizes, the shift of every date's VV against the
series median by phase correlation).
"""
import csv
import json
from collections import Counter, defaultdict

import numpy as np
import rasterio
import shapely
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from scipy import ndimage
from skimage.registration import phase_cross_correlation

from common import ART, HERE, OUT, RAW, UTM, Z
from rank import tile_xy

START = "2017-02-01"


def main():
    items = json.loads((RAW / "rtc_items.json").read_text(encoding="utf-8"))
    by_date = defaultdict(list)
    for it in items:
        d = it["properties"]["datetime"][:10]
        if d >= START:
            by_date[d].append(it)
    dates = sorted(by_date)
    ref = None
    for d in dates:
        for it in by_date[d]:
            for pol in ("vv", "vh"):
                with rasterio.open(RAW / "rtc" / f"{it['id']}_{pol}.tif") as src:
                    g = (tuple(src.transform)[:6], src.shape)
                if ref is None:
                    ref = g
                elif g != ref:
                    raise RuntimeError(f"grid differs: {it['id']} {pol} {g} vs {ref}")
    transform = rasterio.Affine(*ref[0])
    rows, cols = ref[1]
    stack = np.lib.format.open_memmap(ART / "stack.npy", mode="w+", dtype=np.float32, shape=(2, len(dates), rows, cols))
    missing, platforms = [], []
    for t, d in enumerate(dates):
        platforms.append("+".join(sorted({it["properties"]["platform"].upper() for it in by_date[d]})))
        for k, pol in enumerate(("vv", "vh")):
            out = np.full((rows, cols), np.nan, np.float32)
            for it in by_date[d]:
                with rasterio.open(RAW / "rtc" / f"{it['id']}_{pol}.tif") as src:
                    a = src.read(1).astype(np.float32)
                    if src.nodata is not None:
                        a[a == src.nodata] = np.nan
                a[~(a > 0)] = np.nan
                out = np.where(np.isnan(out), a, out)
            stack[k, t] = out
        missing.append(int(np.isnan(stack[0, t]).sum()))
    stack.flush()

    rr, cc = np.mgrid[0:rows, 0:cols]
    x = transform.c + (cc + 0.5) * transform.a
    y = transform.f + (rr + 0.5) * transform.e
    lon, lat = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True).transform(x, y)
    tx, ty = tile_xy(lon, lat, Z)

    wc = np.zeros((rows, cols), np.uint8)
    with rasterio.open(RAW / "worldcover_2021.tif") as src:
        reproject(src.read(1), wc, src_transform=src.transform, src_crs=src.crs, dst_transform=transform, dst_crs=UTM,
                  resampling=Resampling.nearest)

    fc = json.loads((HERE.parent / "labels/site.geojson").read_text(encoding="utf-8"))
    ring = fc["features"][0]["geometry"]["coordinates"][0]
    t = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    poly = shapely.Polygon(list(zip(*t.transform([p[0] for p in ring], [p[1] for p in ring]))))
    site = shapely.contains_xy(poly, x, y)
    dist_site = ndimage.distance_transform_edt(~site) * 10.0
    cx, cy = poly.centroid.x, poly.centroid.y
    dist_centroid = np.hypot(x - cx, y - cy)

    labels = {}
    with open(HERE.parent / "labels/labels.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            labels[(int(r["tile_x"]), int(r["tile_y"]))] = r["label"]
    lab0 = np.vectorize(lambda a, b: labels.get((a, b)) == "0")(tx, ty)
    ctrl = (wc == 50) & lab0 & (dist_centroid <= 1500) & (dist_site >= 100)

    np.savez_compressed(ART / "aux.npz", transform=np.array(tuple(transform)[:6]), dates=np.array(dates),
                        platforms=np.array(platforms), wc=wc, tile_x=tx.astype(np.int32), tile_y=ty.astype(np.int32),
                        site=site, ctrl=ctrl, dist_site=dist_site.astype(np.float32))

    med = np.nanmedian(10 * np.log10(np.asarray(stack[0])), axis=0)
    refimg = np.nan_to_num(med - np.nanmean(med))
    shifts = []
    for ti in range(len(dates)):
        img = 10 * np.log10(np.asarray(stack[0, ti], float))
        img = np.nan_to_num(img - np.nanmean(img))
        s, _, _ = phase_cross_correlation(refimg, img, upsample_factor=20)
        shifts.append([round(float(v), 3) for v in s])
    sh = np.abs(np.array(shifts))
    summary = {
        "grid": {"crs": UTM, "transform": list(tuple(transform)[:6]), "rows": rows, "cols": cols},
        "dates": len(dates), "first": dates[0], "last": dates[-1],
        "dates_per_year": dict(sorted(Counter(d[:4] for d in dates).items())),
        "dates_with_two_items": [d for d in dates if len(by_date[d]) > 1],
        "platforms": dict(Counter(platforms)),
        "fy2019_dates": sum("2019-04-01" <= d <= "2020-03-31" for d in dates),
        "fy2024_dates": sum("2024-04-01" <= d <= "2025-03-31" for d in dates),
        "missing_vv_pixels_max": max(missing), "dates_with_missing": sum(m > 0 for m in missing),
        "site_pixels": int(site.sum()), "site_area_m2": round(poly.area, 1), "ctrl_pixels": int(ctrl.sum()),
        "tile_pixels_min_max": [int(np.unique(tx * 100000 + ty, return_counts=True)[1].min()),
                                int(np.unique(tx * 100000 + ty, return_counts=True)[1].max())],
        "shift_max_rows_cols": [float(sh[:, 0].max()), float(sh[:, 1].max())],
        "dates_shift_over_half_pixel": [dates[i] for i in range(len(dates)) if sh[i].max() > 0.5],
        "shifts": dict(zip(dates, shifts)),
    }
    (OUT / "grid_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print({k: v for k, v in summary.items() if k != "shifts"})


if __name__ == "__main__":
    main()
