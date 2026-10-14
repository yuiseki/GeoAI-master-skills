"""Coarsen a raster by a whole factor, with the one block statistic that keeps the meaning of its kind.

    extensive    sum of the valid pixels in each block (the total is kept exactly)
    intensive    mean of the valid pixels in each block
    categorical  the most frequent class among the valid pixels (a tie goes to the smaller class code)

NoData pixels are left out of each block. A block with no valid pixel stays NoData. Blocks at the right and
bottom edges are partial when the factor does not divide the raster; they hold only the pixels that exist.
The grid stays aligned with the original (same origin and CRS), so units can be aggregated on both and
compared: that is how to see how far a result moves with the resolution.

The blocks are summed in numpy, not with GDAL's warp: on a degree grid whose origin is not a round number,
warp with resampling=sum lost 0.8 % of the total (see the test). The whole band is read into memory.

Usage:
    uvx --with rasterio python coarsen_raster.py RASTER --kind extensive|intensive|categorical --factor 10 \\
        --out coarse.tif [--band 1]
"""

import argparse
import math
import sys

import numpy as np
import rasterio
from rasterio.transform import Affine

RESAMPLING = {"extensive": "sum", "intensive": "average", "categorical": "mode"}


def blocks(a, valid, f):
    """(rows, cols, f*f) views of the data and the valid mask, padding partial edge blocks as not valid."""
    h, w = math.ceil(a.shape[0] / f), math.ceil(a.shape[1] / f)
    pa = np.zeros((h * f, w * f), dtype=a.dtype)
    pv = np.zeros((h * f, w * f), dtype=bool)
    pa[:a.shape[0], :a.shape[1]], pv[:a.shape[0], :a.shape[1]] = a, valid
    def cut(x):
        return x.reshape(h, f, w, f).transpose(0, 2, 1, 3).reshape(h, w, f * f)
    return cut(pa), cut(pv)


def coarsen(raster, kind, factor, out, band=1):
    if kind not in RESAMPLING:
        raise SystemExit(f"--kind must be one of {tuple(RESAMPLING)}")
    with rasterio.open(raster) as src:
        nd = src.nodata
        if nd is None:
            print("warning: the raster declares no NoData value; every pixel is taken as valid", file=sys.stderr)
        a = src.read(band)
        profile = src.profile.copy()
        t = src.transform
    valid = np.ones(a.shape, dtype=bool) if nd is None else a != nd
    if np.issubdtype(a.dtype, np.floating):
        valid &= ~np.isnan(a)
    if a.shape[0] % factor or a.shape[1] % factor:
        print(f"edge blocks are partial: {a.shape[0]} x {a.shape[1]} pixels by {factor}")
    b, v = blocks(a, valid, factor)
    n = v.sum(axis=2)
    fill = nd if nd is not None else np.nan
    if kind == "categorical":
        out_a = np.full(n.shape, fill if nd is not None else 0, dtype=a.dtype)
        best = np.zeros(n.shape, dtype="int64")
        for c in np.unique(a[valid]):  # ascending, so a tie keeps the smaller class
            cnt = ((b == c) & v).sum(axis=2)
            take = cnt > best
            out_a[take], best[take] = c, cnt[take]
        dtype = a.dtype
    else:
        s = np.where(v, b.astype("float64"), 0.0).sum(axis=2)
        val = s if kind == "extensive" else np.divide(s, n, out=np.zeros_like(s), where=n > 0)
        out_a = np.where(n > 0, val, fill).astype("float32")
        dtype = "float32"
    profile.update(height=out_a.shape[0], width=out_a.shape[1], transform=t @ Affine.scale(factor), count=1,
                   dtype=dtype, nodata=nd, tiled=False, compress="deflate")
    profile.pop("blockxsize", None)
    profile.pop("blockysize", None)
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(out_a, 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("raster")
    p.add_argument("--kind", required=True, choices=tuple(RESAMPLING))
    p.add_argument("--factor", type=int, required=True)
    p.add_argument("--band", type=int, default=1)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    coarsen(a.raster, a.kind, a.factor, a.out, a.band)


if __name__ == "__main__":
    main()
