"""Small pieces of the analysis, tested in test_water_stats.py.

  best_shift      the integer shift s (rows, cols) within +-r that maximises the correlation of mask[i] and img[i + s]
  shifted         img read at i + s, NaN where i + s leaves the grid
  pond_fractions  per pond id, the number of valid pixels and the share of them that are water
  twoway_resid    x minus its group means in two crossed groupings (pond, date), by alternating projections
  pair_dates      for each S1 date, the nearest S2 date within the window (the earlier one on a tie)
"""

from datetime import date

import numpy as np
from scipy import ndimage


def shifted(img, s):
    dy, dx = s
    h, w = img.shape
    out = np.full(img.shape, np.nan, dtype="float64")
    ys = slice(max(0, -dy), min(h, h - dy))
    xs = slice(max(0, -dx), min(w, w - dx))
    out[ys, xs] = img[ys.start + dy:ys.stop + dy, xs.start + dx:xs.stop + dx]
    return out


def best_shift(mask, img, r=5, where=None):
    """where: optional boolean raster; only these pixels enter the correlation (e.g. land near the ponds)."""
    best, best_c = (0, 0), -np.inf
    m = mask.astype("float64")
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            v = shifted(img, (dy, dx))
            ok = ~np.isnan(v) if where is None else (~np.isnan(v) & where)
            if ok.sum() < 100:
                continue
            c = np.corrcoef(m[ok], v[ok])[0, 1]
            if c > best_c:
                best, best_c = (dy, dx), c
    return best, float(best_c)


def pond_fractions(labels, valid, water, ids):
    """labels: pond id raster; valid, water: boolean rasters. Returns (n_valid, frac) arrays aligned with ids."""
    n = ndimage.sum_labels(valid.astype("int64"), labels, index=ids)
    wat = ndimage.sum_labels((valid & water).astype("int64"), labels, index=ids)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(n > 0, wat / np.maximum(n, 1), np.nan)
    return n.astype(int), frac


def twoway_resid(x, a, b, iters=200, tol=1e-12):
    """x minus the means of groups a and b (unbalanced), i.e. the residual of x ~ a + b."""
    r = np.asarray(x, dtype="float64") - np.mean(x)
    a = np.unique(a, return_inverse=True)[1]
    b = np.unique(b, return_inverse=True)[1]
    for _ in range(iters):
        r_old = r.copy()
        for g in (a, b):
            means = np.bincount(g, weights=r) / np.bincount(g)
            r = r - means[g]
        if np.max(np.abs(r - r_old)) < tol:
            break
    return r


def pair_dates(s1_dates, s2_dates, window_days=2):
    d2 = sorted(s2_dates)
    out = {}
    for d1 in s1_dates:
        t1 = date.fromisoformat(d1)
        cands = [(abs((date.fromisoformat(d) - t1).days), d) for d in d2]
        cands = [c for c in cands if c[0] <= window_days]
        if cands:
            out[d1] = min(cands)[1]
    return out
