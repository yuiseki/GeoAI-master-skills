"""Baseline, metrics and tiling for binary segmentation of image chips (water / not water and the like), tested in
test_seg_eval.py. Labels use IGNORE (255) for invalid pixels.

  otsu_threshold, otsu_mask   Otsu's threshold of one chip's values (256 bins between the 0.1% and 99.9% values);
                              the mask marks the values at or below it (dark = water for SAR backscatter in dB)
  chip_iou                    IoU of the positive class on one chip, invalid pixels left out,
                              (intersection + 1e-7) / (union + 1e-7): a chip with no positive in either scores 1
  pooled_iou                  IoU over all pixels of all chips
  tiles, untile               a square chip as non-overlapping tiles (row by row) and back
  random_crop_flip            a random crop with random horizontal and vertical flips of image and label together
  boot_by_group               95% interval of a mean, resampling whole groups (events, scenes)
  paired_difference           mean of a - b on the same chips, with the group-resampled interval
"""

import numpy as np

IGNORE = 255
EPS = 1e-7


def otsu_threshold(values, bins=256):
    v = np.asarray(values, dtype="float64")
    v = v[np.isfinite(v)]
    lo, hi = np.percentile(v, [0.1, 99.9])
    if hi <= lo:
        return float(lo)
    h, edges = np.histogram(np.clip(v, lo, hi), bins=bins, range=(lo, hi))
    centres = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(h)
    w1 = w0[-1] - w0
    s0 = np.cumsum(h * centres)
    m0 = s0 / np.maximum(w0, 1)
    m1 = (s0[-1] - s0) / np.maximum(w1, 1)
    between = w0 * w1 * (m0 - m1) ** 2
    return float(edges[1:][np.argmax(between)])


def otsu_mask(img):
    img = np.asarray(img, dtype="float64")
    ok = np.isfinite(img)
    if not ok.any():
        return np.zeros(img.shape, dtype="int64")
    v = img[ok]
    if v.max() == v.min():
        return np.zeros(img.shape, dtype="int64")
    t = otsu_threshold(v)
    return (ok & (np.nan_to_num(img, nan=np.inf) <= t)).astype("int64")


def _iu(pred, target):
    target = np.asarray(target)
    ok = target != IGNORE
    p, t = np.asarray(pred)[ok] == 1, target[ok] == 1
    i = np.sum(p & t)
    return i, np.sum(p) + np.sum(t) - i


def chip_iou(pred, target):
    i, u = _iu(pred, target)
    return float((i + EPS) / (u + EPS))


def pooled_iou(preds, targets):
    iu = np.array([_iu(p, t) for p, t in zip(preds, targets)])
    return float(iu[:, 0].sum() / iu[:, 1].sum())


def tiles(a, size):
    n = a.shape[-1] // size
    return np.stack([a[..., r * size:(r + 1) * size, c * size:(c + 1) * size] for r in range(n) for c in range(n)])


def untile(t, full):
    n = full // t.shape[-1]
    rows = [np.concatenate([t[r * n + c] for c in range(n)], -1) for r in range(n)]
    return np.concatenate(rows, -2)


def random_crop_flip(x, y, size, rng):
    h, w = y.shape
    i, j = rng.integers(0, h - size + 1), rng.integers(0, w - size + 1)
    cx, cy = x[:, i:i + size, j:j + size], y[i:i + size, j:j + size]
    if rng.random() > 0.5:
        cx, cy = cx[:, :, ::-1], cy[:, ::-1]
    if rng.random() > 0.5:
        cx, cy = cx[:, ::-1, :], cy[::-1, :]
    return np.ascontiguousarray(cx), np.ascontiguousarray(cy)


def boot_by_group(x, group, reps=2000, seed=0):
    rng = np.random.default_rng(seed)
    g = np.unique(group, return_inverse=True)[1]
    sums, cnt = np.bincount(g, x), np.bincount(g)
    idx = rng.integers(0, len(sums), (reps, len(sums)))
    return tuple(float(v) for v in np.percentile(sums[idx].sum(1) / cnt[idx].sum(1), [2.5, 97.5]))


def paired_difference(a, b, group, reps=2000, seed=0):
    d = np.asarray(a, dtype="float64") - np.asarray(b, dtype="float64")
    lo, hi = boot_by_group(d, group, reps, seed)
    return float(d.mean()), lo, hi


def focal_mean(img, size):
    """Mean over a size x size window, ignoring NaN (a box filter; the window the Sen1Floods11 authors used is not
    stated, 5 pixels reproduced 99% of their labels)."""
    from scipy.ndimage import uniform_filter
    img = np.asarray(img, dtype="float64")
    ok = np.isfinite(img)
    s = uniform_filter(np.where(ok, img, 0.0), size, mode="nearest")
    c = uniform_filter(ok.astype("float64"), size, mode="nearest")
    return np.where(c > 0, s / np.maximum(c, 1e-12), np.nan)


def scene_otsu_threshold(img, cell=100, top=0.1, min_valid=0.5):
    """One threshold for a whole scene: cut it into cell x cell squares, keep the `top` share with the highest
    standard deviation (squares holding both water and land), and run Otsu on their pooled values."""
    img = np.asarray(img, dtype="float64")
    h, w = img.shape[-2:]
    cells = []
    for r in range(0, h - cell + 1, cell):
        for c in range(0, w - cell + 1, cell):
            v = img[r:r + cell, c:c + cell]
            v = v[np.isfinite(v)]
            if len(v) >= min_valid * cell * cell:
                cells.append((v.std(), v))
    if not cells:
        return otsu_threshold(img.ravel())
    cells.sort(key=lambda x: -x[0])
    k = max(1, int(round(top * len(cells))))
    return otsu_threshold(np.concatenate([v for _, v in cells[:k]]))
