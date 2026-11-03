"""Small parts of the analysis, tested in test_flood.py: smoothing, the change in dB, the land-cover standardised rate,
the units of the bootstrap (connected components, 1 km blocks), the bootstrap, the lift, and the shift of the image
against a water mask."""
import numpy as np
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


def _unit_sums(flag, units):
    u, inv = np.unique(units, return_inverse=True)
    return np.bincount(inv, weights=flag.astype(float)), np.bincount(inv).astype(float)


def _draws(flag, units, n, rng):
    s, c = _unit_sums(np.asarray(flag), np.asarray(units))
    idx = rng.integers(0, len(s), size=(n, len(s)))
    return s[idx].sum(1) / c[idx].sum(1)


def bootstrap_rate(flag, units, n=2000, seed=0, q=(0.05, 0.95)):
    """90 % interval of the rate of flag, resampling whole units with replacement."""
    d = _draws(flag, units, n, np.random.default_rng(seed))
    return float(np.quantile(d, q[0])), float(np.quantile(d, q[1]))


def bootstrap_ratio(f1, u1, f2, u2, n=2000, seed=0, q=(0.05, 0.95)):
    """90 % interval of rate(f1) / rate(f2), the two groups resampled independently by their units."""
    rng = np.random.default_rng(seed)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = _draws(f1, u1, n, rng) / _draws(f2, u2, n, rng)
    return float(np.quantile(d, q[0])), float(np.quantile(d, q[1]))


def lift(flag, in_a, pop):
    """P(in_a | flag) / P(in_a), within pop."""
    flag, in_a, pop = (np.asarray(v, bool) for v in (flag, in_a, pop))
    return float(in_a[flag & pop].mean() / in_a[pop].mean())


def shift_against_mask(db, water):
    """(rows, cols) to move the image by so that it lines up with the water mask (phase correlation, 1/20 pixel)."""
    from skimage.registration import phase_cross_correlation
    img = np.nan_to_num(-(db - np.nanmean(db)))  # water is dark: flip so that water is high like the mask
    ref = water.astype(float) - water.mean()
    s, _, _ = phase_cross_correlation(ref, img, upsample_factor=20)
    return float(s[0]), float(s[1])


def apply_int_shift(a, s):
    """Move the content of a by the rounded (rows, cols) s: out[i + dr, j + dc] = a[i, j]; nan where nothing lands."""
    dr, dc = int(round(s[0])), int(round(s[1]))
    out = np.full(a.shape, np.nan)
    r0, r1 = max(dr, 0), a.shape[0] + min(dr, 0)
    c0, c1 = max(dc, 0), a.shape[1] + min(dc, 0)
    out[r0:r1, c0:c1] = a[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
    return out


def rate_draws(flag, units, n, rng):
    """Bootstrap draws of the rate of flag, resampling whole units."""
    return _draws(flag, units, n, rng)


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


def lift_draws(flag, in_a, units, n, rng):
    """Bootstrap draws of lift(flag, in_a, all), resampling whole units."""
    flag, in_a = np.asarray(flag, bool), np.asarray(in_a, bool)
    u, inv = np.unique(units, return_inverse=True)
    fa = np.bincount(inv, weights=(flag & in_a).astype(float))
    f = np.bincount(inv, weights=flag.astype(float))
    a = np.bincount(inv, weights=in_a.astype(float))
    t = np.bincount(inv).astype(float)
    out = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, len(u), len(u))
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i] = (fa[idx].sum() / f[idx].sum()) / (a[idx].sum() / t[idx].sum())
    return out
