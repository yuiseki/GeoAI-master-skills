"""Print what a raster band holds, before deciding how to aggregate it.

Grid: CRS, shape, resolution (and, for a geographic raster, the pixel size in metres at the centre), bounds,
transform, dtype. Values: the NoData value, scale and offset, and over the pixels read: how many are valid,
NoData, NaN, and 0 among the valid ones (0 and NoData are different things), min, max, sum and mean of the
valid values with scale and offset applied. For an integer band, the count of each value (up to --max-values
distinct values), which is how a class code raster shows itself.

The band is read block by block, so a large file does not need to fit in memory. --bbox (in the raster's
CRS) reads only that window.

Usage:
    uvx --with rasterio --with pyproj python inspect_raster.py RASTER [--band 1] [--bbox MINX MINY MAXX MAXY] [--max-values 50]
"""

import argparse
import math

import numpy as np
import pyproj
import rasterio
from rasterio.errors import WindowError
from rasterio.windows import Window, from_bounds


def inspect(raster, band=1, bbox=None, max_values=50):
    with rasterio.open(raster) as ds:
        t = ds.transform
        nd = ds.nodatavals[band - 1]
        scale, offset = ds.scales[band - 1], ds.offsets[band - 1]
        r = {
            "crs": ds.crs.to_string() if ds.crs else None, "geographic": bool(ds.crs and ds.crs.is_geographic),
            "height": ds.height, "width": ds.width, "resolution": (abs(t.a), abs(t.e)), "bounds": tuple(ds.bounds),
            "transform": tuple(t)[:6], "dtype": ds.dtypes[band - 1], "nodata_value": nd, "scale": scale,
            "offset": offset, "units": ds.units[band - 1] or None, "description": ds.descriptions[band - 1],
        }
        if r["geographic"]:
            lon, lat = (ds.bounds.left + ds.bounds.right) / 2, (ds.bounds.bottom + ds.bounds.top) / 2
            g = pyproj.Geod(ellps="WGS84")
            ew = g.inv(lon, lat, lon + abs(t.a), lat)[2]
            ns = g.inv(lon, lat, lon, lat + abs(t.e))[2]
            r["pixel_m_at_centre"] = (round(ew, 2), round(ns, 2))

        win = Window(0, 0, ds.width, ds.height)
        if bbox:
            win = from_bounds(*bbox, transform=t).round_offsets().round_lengths()
            try:
                win = win.intersection(Window(0, 0, ds.width, ds.height))
            except WindowError:
                raise SystemExit(f"--bbox {bbox} does not overlap the raster {tuple(ds.bounds)}; "
                                 f"give it in the raster's CRS, {r['crs']}")
        integer = np.issubdtype(np.dtype(r["dtype"]), np.integer)
        n = valid = nodata = nan = zero = 0
        vmin, vmax, vsum, values = math.inf, -math.inf, 0.0, {}
        step = 1024
        for row in range(int(win.row_off), int(win.row_off + win.height), step):
            h = min(step, int(win.row_off + win.height) - row)
            a = ds.read(band, window=Window(win.col_off, row, win.width, h))
            ok = np.ones(a.shape, dtype=bool)
            if nd is not None and not (isinstance(nd, float) and math.isnan(nd)):
                nodata += int((a == nd).sum())
                ok &= a != nd
            if np.issubdtype(a.dtype, np.floating):
                isn = np.isnan(a)
                nan += int(isn.sum())
                ok &= ~isn
            n += a.size
            v = a[ok].astype("float64") * scale + offset
            valid += v.size
            if v.size:
                zero += int((v == 0).sum())
                vmin, vmax, vsum = min(vmin, v.min()), max(vmax, v.max()), vsum + v.sum()
            if integer and values is not None:
                for k, c in zip(*np.unique(a[ok], return_counts=True)):
                    values[int(k)] = values.get(int(k), 0) + int(c)
                if len(values) > max_values:
                    values = None
        r.update(pixels=n, valid=valid, nodata=nodata, nan=nan, zero=zero,
                 min=vmin if valid else None, max=vmax if valid else None, sum=vsum if valid else None,
                 mean=vsum / valid if valid else None)
        if integer:
            r["values"] = values  # None when there were more than max_values distinct values
    return r


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("raster")
    p.add_argument("--band", type=int, default=1)
    p.add_argument("--bbox", type=float, nargs=4, metavar=("MINX", "MINY", "MAXX", "MAXY"))
    p.add_argument("--max-values", type=int, default=50)
    a = p.parse_args()
    for k, v in inspect(a.raster, a.band, a.bbox, a.max_values).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
