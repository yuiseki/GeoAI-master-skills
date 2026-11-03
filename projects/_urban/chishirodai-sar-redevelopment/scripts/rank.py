"""Small helpers for the tile ranking (B) and the optical dating (A2). Tested in test_rank.py."""
import math

import numpy as np


def tile_xy(lon, lat, z):
    """Web-mercator tile (x, y) containing the point; works on scalars and arrays."""
    n = 2 ** z
    x = np.floor((np.asarray(lon, float) + 180) / 360 * n).astype(int)
    y = np.floor((1 - np.arcsinh(np.tan(np.radians(np.asarray(lat, float)))) / math.pi) / 2 * n).astype(int)
    x, y = np.clip(x, 0, n - 1), np.clip(y, 0, n - 1)
    if x.ndim == 0:
        return int(x), int(y)
    return x, y


def rank_order(scores, ids):
    """Ids sorted by score, largest first; ties go to the smaller id."""
    return [i for _, i in sorted(zip(scores, ids), key=lambda t: (-t[0], t[1]))]


def recall_at(scores, ids, positives, k):
    """Share of the positive ids among the top k of rank_order."""
    if not positives:
        raise ValueError("no positives")
    top = set(rank_order(scores, ids)[:k])
    return len(top & set(positives)) / len(positives)


def hypergeom_tail(m, N, K, n):
    """P(at least m positives) when n of N items (K positive) are drawn at random without replacement."""
    tot = math.comb(N, n)
    return sum(math.comb(K, k) * math.comb(N - K, n - k) for k in range(m, min(K, n) + 1)) / tot


def break_2seg(y, min_seg=5):
    """The split of the rows of y (time x variables) into two segments with the smallest within-segment sum of squares.

    Returns (k, sse): the first row of the second segment, and the sum of squares for every candidate k (nan where a
    segment would be shorter than min_seg).
    """
    y = np.asarray(y, float)
    if y.ndim == 1:
        y = y[:, None]
    n = len(y)
    sse = np.full(n, np.nan)
    for k in range(min_seg, n - min_seg + 1):
        a, b = y[:k], y[k:]
        sse[k] = ((a - a.mean(0)) ** 2).sum() + ((b - b.mean(0)) ** 2).sum()
    if not np.isfinite(sse).any():
        raise ValueError("series too short")
    return int(np.nanargmin(sse)), sse
