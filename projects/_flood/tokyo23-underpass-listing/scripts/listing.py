"""Shares, differences of shares and the block bootstrap of EXPERIMENT_PLAN.md."""
import numpy as np


def grid_blocks(x, y, size=2000.0):
    """Block id of each point on a square grid of the given size (same units as x, y)."""
    gx = np.floor(np.asarray(x) / size).astype(np.int64)
    gy = np.floor(np.asarray(y) / size).astype(np.int64)
    _, ids = np.unique(np.column_stack([gx, gy]), axis=0, return_inverse=True)
    return ids.ravel()


def share(a):
    a = np.asarray(a, bool)
    return float(a.mean()) if len(a) else np.nan


def diff_share(outcome, group):
    """share(outcome | group) - share(outcome | not group)."""
    outcome, group = np.asarray(outcome, bool), np.asarray(group, bool)
    return share(outcome[group]) - share(outcome[~group])


def block_bootstrap(blocks, stat, n=2000, seed=0, q=(5, 95)):
    """Percentile interval of stat(index) over resamples of whole blocks with replacement. stat takes an index array
    into the units and returns a number (nan is dropped). Returns (low, high, n_used)."""
    blocks = np.asarray(blocks)
    uniq = np.unique(blocks)
    members = {b: np.where(blocks == b)[0] for b in uniq}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([members[b] for b in pick])
        v = stat(idx)
        if not np.isnan(v):
            vals.append(v)
    lo, hi = np.percentile(vals, q)
    return float(lo), float(hi), len(vals)


def verdict(lo, hi, threshold):
    """支持 when the interval lies above the threshold, 退ける when at or below it, else 判定できない."""
    if lo > threshold:
        return "支持"
    if hi <= threshold:
        return "退ける"
    return "判定できない"


def verdict_below(lo, hi, threshold):
    """For a claim that a value is under the threshold: 支持 when hi < threshold, 退ける when lo >= threshold."""
    if hi < threshold:
        return "支持"
    if lo >= threshold:
        return "退ける"
    return "判定できない"
