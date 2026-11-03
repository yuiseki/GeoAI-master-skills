"""Share of pixels that got darker and brighter in each group, against a control with the same land-cover mix.

uvx --with numpy --with scipy --with rasterio python change_rates.py --delta tmp/delta.tif --groups tmp/groups.tif \
  --classes tmp/landcover.tif --control 9 --threshold 3 --block 1000 [--components 1,2] --n 2000 --seed 0 > rates.json

Inputs are single-band GeoTIFFs on one grid (the script stops otherwise):
- --delta: the change in dB (sar_change.py), nan where missing.
- --groups: an integer code per pixel; 0 is outside every group. --control names the code of the control group.
- --classes: an integer land-cover class per pixel.

For each group: n, and for darker (delta <= -threshold) and brighter (delta >= +threshold):
- rate: the share of the group's pixels.
- control: the control's rate per class, weighted by the group's class mix (direct standardisation). Classes with
  fewer than --min-class control pixels are left out; control_dropped_share is the share of the group's pixels in them.
- ratio = rate / control (null when the control rate is 0), and 90 % intervals of rate, control and ratio from --n
  bootstrap draws. Whole units are resampled, not pixels, because neighbouring pixels are alike: --block x --block
  squares (in the CRS units) for every group, or the 8-connected components of the group for the codes in
  --components. The group and the control are resampled independently.
Every pixel is counted: pixels = missing (delta nan) + outside (code 0) + the n of each group.
"""
import argparse
import json
import sys

import numpy as np
import rasterio
from scipy import ndimage


def standardized_rate(flag, cls, target, ref, min_n=1000):
    """The rate of flag in ref, reweighted to the class mix of target (direct standardisation).

    Classes with fewer than min_n ref pixels are left out of both; dropped_share is the share of target pixels in them.
    """
    flag, cls, target, ref = (np.asarray(v) for v in (flag, cls, target, ref))
    classes, counts = np.unique(cls[target], return_counts=True)
    keep, w, rates, dropped = [], [], [], []
    for c, n in zip(classes, counts):
        m = ref & (cls == c)
        if m.sum() < min_n:
            dropped.append(int(c))
            continue
        keep.append(int(c))
        w.append(n)
        rates.append(flag[m].mean())
    w = np.array(w, float)
    rate = float(np.dot(w, rates) / w.sum()) if w.sum() else float("nan")
    return {"rate": rate, "classes": keep, "dropped_classes": dropped,
            "dropped_share": float(1 - w.sum() / counts.sum()) if counts.sum() else float("nan"),
            "weights": {c: float(x / w.sum()) for c, x in zip(keep, w)},
            "class_rates": {c: float(r) for c, r in zip(keep, rates)}}


def components(mask):
    """Label of the 8-connected component of each True pixel (0 elsewhere)."""
    lab, _ = ndimage.label(mask, structure=np.ones((3, 3), int))
    return lab


def block_ids(x, y, size):
    """An integer id of the size x size block (in the units of x and y) of each point."""
    bx = np.floor(np.asarray(x) / size).astype(np.int64)
    by = np.floor(np.asarray(y) / size).astype(np.int64)
    return bx * 1_000_003 + by


def rate_draws(flag, units, n, rng):
    """Bootstrap draws of the rate of flag, resampling whole units."""
    u, inv = np.unique(np.asarray(units), return_inverse=True)
    s = np.bincount(inv, weights=np.asarray(flag, float))
    c = np.bincount(inv).astype(float)
    idx = rng.integers(0, len(s), size=(n, len(s)))
    return s[idx].sum(1) / c[idx].sum(1)


def std_rate_draws(flag, cls, units, weights, n, rng):
    """Bootstrap draws of the standardised rate sum_c weights[c] * rate_c, resampling whole units of the reference.

    weights: {class: weight}, summing to 1 over the classes kept."""
    flag, cls, units = np.asarray(flag), np.asarray(cls), np.asarray(units)
    u, inv = np.unique(units, return_inverse=True)
    cs = list(weights)
    S = np.stack([np.bincount(inv, weights=(flag & (cls == c)).astype(float), minlength=len(u)) for c in cs], 1)
    C = np.stack([np.bincount(inv, weights=(cls == c).astype(float), minlength=len(u)) for c in cs], 1)
    w = np.array([weights[c] for c in cs])
    out = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, len(u), len(u))
        s, c = S[idx].sum(0), C[idx].sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i] = np.dot(w, s / c)
    return out


def q90(d):
    d = d[np.isfinite(d)]
    return [round(float(np.quantile(d, 0.05)), 4), round(float(np.quantile(d, 0.95)), 4)] if d.size else None


def read(path, grid=None):
    with rasterio.open(path) as src:
        g = (src.crs, src.transform, src.shape)
        a = src.read(1)
        nodata = src.nodata
    if grid is not None and g != grid:
        sys.exit(f"{path}: the grid (crs, transform, shape) differs from --delta: {g} != {grid}")
    return a, g, nodata


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--delta", required=True)
    p.add_argument("--groups", required=True)
    p.add_argument("--classes", required=True)
    p.add_argument("--control", type=int, required=True)
    p.add_argument("--threshold", type=float, default=3.0)
    p.add_argument("--block", type=float, default=1000.0)
    p.add_argument("--components", default="")
    p.add_argument("--min-class", type=int, default=1000)
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)

    d, grid, nd = read(a.delta)
    d = d.astype(float)
    if nd is not None and np.isfinite(nd):
        d[d == nd] = np.nan
    grp = read(a.groups, grid)[0].astype(np.int64)
    cls = read(a.classes, grid)[0].astype(np.int64)
    ok = np.isfinite(d)
    codes = sorted(int(c) for c in np.unique(grp[ok]) if c != 0)
    if a.control not in codes:
        sys.exit(f"the control code {a.control} has no valid pixel (codes with valid pixels: {codes})")
    comp_codes = {int(c) for c in a.components.split(",") if c}

    t = grid[1]
    rows, cols = np.indices(grp.shape)
    x, y = t.c + (cols + 0.5) * t.a, t.f + (rows + 0.5) * t.e
    blocks = block_ids(x, y, a.block)
    out = {"pixels": int(d.size), "missing": int((~ok).sum()), "outside": int((ok & (grp == 0)).sum()),
           "threshold_db": a.threshold, "block": a.block, "components": sorted(comp_codes), "n_draws": a.n,
           "seed": a.seed, "groups": {}}
    ctrl = ok & (grp == a.control)
    total = out["missing"] + out["outside"]
    for code in codes:
        m = ok & (grp == code)
        total += int(m.sum())
        units = components(grp == code)[m] if code in comp_codes else blocks[m]
        g = {"n": int(m.sum()), "units": int(len(np.unique(units)))}
        if code != a.control:
            ref = standardized_rate(d <= -a.threshold, cls, m, ctrl, a.min_class)
            g["control_classes"] = ref["classes"]
            g["control_dropped_share"] = round(ref["dropped_share"], 4)
        for name, flag in (("darker", d <= -a.threshold), ("brighter", d >= a.threshold)):
            rng = np.random.default_rng(a.seed)
            rate = float(flag[m].mean())
            gd = rate_draws(flag[m], units, a.n, rng)
            r = {"rate": round(rate, 4), "rate_90": q90(gd)}
            if code != a.control:
                sr = standardized_rate(flag, cls, m, ctrl, a.min_class)
                cd = std_rate_draws(flag[ctrl], cls[ctrl], blocks[ctrl], sr["weights"], a.n, rng)
                r["control"] = round(sr["rate"], 4)
                r["control_90"] = q90(cd)
                r["ratio"] = round(rate / sr["rate"], 4) if sr["rate"] > 0 else None
                with np.errstate(divide="ignore", invalid="ignore"):
                    r["ratio_90"] = q90(gd / cd) if sr["rate"] > 0 else None
            g[name] = r
        out["groups"][str(code)] = g
    if total != out["pixels"]:
        sys.exit(f"the pixel counts do not add up: {total} != {out['pixels']}")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
