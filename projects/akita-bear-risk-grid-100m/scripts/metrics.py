"""Ranking scores of a risk map: capture@k (the share of the positive cells that fall in the top k of all cells),
weighted for block bootstrap, and the block-bootstrap interval of the difference between two maps.

The order of the cells is fixed once per map (rank_order): by the score, then by a second key, then at random
with a fixed seed, so ties are broken the same way for every resample. The cut at k of the total weight takes
the cell that straddles it by its fraction.
"""

import numpy as np


def rank_order(score, second=None, seed=0):
    rng = np.random.default_rng(seed)
    keys = [rng.random(len(score))]
    if second is not None:
        keys.append(-np.nan_to_num(np.asarray(second, dtype=float), nan=-np.inf))
    keys.append(-np.nan_to_num(np.asarray(score, dtype=float), nan=-np.inf))
    return np.lexsort(keys)


def capture(order, pos, k, weights=None):
    w = np.ones(len(order)) if weights is None else np.asarray(weights, dtype=float)
    wo = w[order]
    po = np.asarray(pos)[order]
    total_pos = float((w * pos).sum())
    if total_pos == 0:
        return float("nan")
    cut = k * wo.sum()
    cum = np.cumsum(wo)
    prev = cum - wo
    take = np.clip((cut - prev) / np.where(wo > 0, wo, 1), 0, 1) * (wo > 0)
    return float((take * wo * po).sum() / total_pos)


def bootstrap_diff(order_a, order_b, pos, blocks, k, B=1000, seed=0):
    """90% interval of capture(a) - capture(b), resampling whole blocks with replacement."""
    ids, inv = np.unique(blocks, return_inverse=True)
    rng = np.random.default_rng(seed)
    diffs = np.empty(B)
    for b in range(B):
        mult = np.bincount(rng.integers(0, len(ids), len(ids)), minlength=len(ids)).astype(float)
        w = mult[inv]
        diffs[b] = capture(order_a, pos, k, w) - capture(order_b, pos, k, w)
    return float(np.quantile(diffs, 0.05)), float(np.quantile(diffs, 0.95)), diffs
