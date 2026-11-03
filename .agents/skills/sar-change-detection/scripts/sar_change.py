"""The change in backscatter between the scenes before an event and one scene after it, in dB.

uvx --with numpy --with scipy --with scikit-image --with rasterio python sar_change.py \
  --pre tmp/pre_*.tif --post tmp/post.tif --k 3 --threshold 3 [--water tmp/water.tif] --out tmp/delta.tif

Inputs are single-band GeoTIFFs on one grid (same CRS, transform and shape; the script stops otherwise), holding linear
backscatter (gamma0 or sigma0 in power, not dB). The file's NoData, nan and values <= 0 are missing.

1. The pre scenes are averaged in linear power (a pixel missing in some pre scenes uses the others).
2. The pre mean and the post scene are each smoothed by a k x k mean (ignoring missing pixels), against speckle.
3. The change is 10 log10(post / pre) in dB, written as float32 with nan where either side is missing.
4. With --water (a 0/1 raster on the same grid, e.g. permanent water), the shift of the pre mean against the mask is
   measured by phase correlation. If either component is over --max-shift pixels, the change is moved back by the
   rounded shift (pixels that nothing lands on become nan). The shift of the post scene against the pre mean is also
   measured and printed: the change is only meaningful if it is near 0.

Prints a JSON summary: pixels, valid, no_pre, no_post (counted on the unsmoothed inputs and adding up to pixels),
darker and brighter (pixels at or beyond -threshold and +threshold among the valid ones after the shift), the shifts.
"""
import argparse
import json
import sys
import warnings

import numpy as np
import rasterio
from scipy import ndimage


def boxcar(a, k):
    """Mean over a k x k window, ignoring nan; nan where the whole window is nan. k = 1 returns a copy."""
    a = np.asarray(a, float)
    if k == 1:
        return a.copy()
    ok = np.isfinite(a)
    s = ndimage.uniform_filter(np.where(ok, a, 0.0), k, mode="constant")
    n = ndimage.uniform_filter(ok.astype(float), k, mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = s / n
    out[n < 1e-9] = np.nan
    return out


def ratio_db(post, pre):
    with np.errstate(invalid="ignore", divide="ignore"):
        return 10 * np.log10(np.asarray(post, float) / np.asarray(pre, float))


def change_db(pre, post, k):
    """pre: list of linear arrays (nan = missing). The mean is taken in linear power, then both sides are smoothed."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pre_mean = np.nanmean(np.stack([np.asarray(p, float) for p in pre]), axis=0)
    return ratio_db(boxcar(post, k), boxcar(pre_mean, k))


def shift_against_mask(db, water):
    """(rows, cols) to move the image by so that it lines up with the water mask (phase correlation, 1/20 pixel)."""
    from skimage.registration import phase_cross_correlation
    img = np.nan_to_num(-(db - np.nanmean(db)))  # water is dark: flip it so that water is high like the mask
    ref = water.astype(float) - water.mean()
    s, _, _ = phase_cross_correlation(ref, img, upsample_factor=20)
    return float(s[0]), float(s[1])


def shift_between(ref_db, img_db):
    """(rows, cols) to move img by so that it lines up with ref (both in dB, phase correlation, 1/20 pixel)."""
    from skimage.registration import phase_cross_correlation
    a = np.nan_to_num(ref_db - np.nanmean(ref_db))
    b = np.nan_to_num(img_db - np.nanmean(img_db))
    s, _, _ = phase_cross_correlation(a, b, upsample_factor=20)
    return float(s[0]), float(s[1])


def apply_int_shift(a, s):
    """Move the content of a by the rounded (rows, cols) s: out[i + dr, j + dc] = a[i, j]; nan where nothing lands."""
    dr, dc = int(round(s[0])), int(round(s[1]))
    out = np.full(a.shape, np.nan)
    r0, r1 = max(dr, 0), a.shape[0] + min(dr, 0)
    c0, c1 = max(dc, 0), a.shape[1] + min(dc, 0)
    out[r0:r1, c0:c1] = a[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
    return out


def read(path, grid=None):
    with rasterio.open(path) as src:
        g = (src.crs, src.transform, src.shape)
        a = src.read(1).astype(float)
        if src.nodata is not None:
            a[a == src.nodata] = np.nan
        profile = src.profile
    if grid is not None and g != grid:
        sys.exit(f"{path}: the grid (crs, transform, shape) differs from the first file: {g} != {grid}")
    return a, g, profile


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--pre", nargs="+", required=True)
    p.add_argument("--post", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--threshold", type=float, default=3.0)
    p.add_argument("--water")
    p.add_argument("--max-shift", type=float, default=1.0)
    a = p.parse_args(argv)

    first, grid, profile = read(a.pre[0])
    pre = [first] + [read(f, grid)[0] for f in a.pre[1:]]
    post = read(a.post, grid)[0]
    for x in pre + [post]:
        x[~(x > 0)] = np.nan  # nan and values <= 0 are missing
    no_post = ~np.isfinite(post)
    no_pre = ~np.isfinite(np.stack(pre)).any(0) & ~no_post
    pixels = post.size
    valid = int((~no_post & ~no_pre).sum())
    if valid + int(no_post.sum()) + int(no_pre.sum()) != pixels:
        sys.exit("the pixel counts do not add up")

    d = change_db(pre, post, a.k)
    d[no_post | no_pre] = np.nan
    summary = {"pixels": pixels, "valid": valid, "no_pre": int(no_pre.sum()), "no_post": int(no_post.sum()),
               "n_pre": len(pre), "k": a.k, "threshold_db": a.threshold}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pre_db = 10 * np.log10(np.nanmean(np.stack(pre), axis=0))
    if a.water:
        water = read(a.water, grid)[0] > 0
        s = shift_against_mask(pre_db, water)
        summary["pre_vs_water_shift_rows_cols"] = [round(s[0], 3), round(s[1], 3)]
        applied = [int(round(v)) for v in s] if max(abs(v) for v in s) > a.max_shift else [0, 0]
        summary["shift_applied_rows_cols"] = applied
        if any(applied):
            d = apply_int_shift(d, applied)
    sp = shift_between(pre_db, 10 * np.log10(post))
    summary["post_vs_pre_shift_rows_cols"] = [round(sp[0], 3), round(sp[1], 3)]
    ok = np.isfinite(d)
    summary["valid_after_shift"] = int(ok.sum())
    summary["darker"] = int((d[ok] <= -a.threshold).sum())
    summary["brighter"] = int((d[ok] >= a.threshold).sum())

    profile.update(driver="GTiff", dtype="float32", count=1, nodata=np.nan, compress="deflate")
    with rasterio.open(a.out, "w", **profile) as dst:
        dst.write(d.astype("float32"), 1)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
