"""The phase space of the bear-side and human-side proxies, the year-shift statistics on it, and the null shuffles.

Each axis is a model score turned into its percentile over all prefecture cells (average rank / number of cells,
so ties share a value), cut into five equal bands (q1 low, q5 high). The 25 bins are grouped into six regions,
fixed in EXPERIMENT_PLAN.md before any result was seen. Nothing here fits a model.
"""

import numpy as np

REGIONS = ("bear_core", "contact", "boundary", "human_core", "low_both", "other")


def percentile(score):
    from scipy.stats import rankdata

    return rankdata(score, method="average") / len(score)


def quintile(p):
    return np.clip(np.ceil(np.asarray(p) * 5 - 1e-12), 1, 5).astype(int)


def region(b, h):
    if b >= 4 and h <= 2:
        return "bear_core"
    if b >= 4 and h >= 4:
        return "contact"
    if (b, h) in ((3, 3), (3, 4), (4, 3)):
        return "boundary"
    if b <= 2 and h >= 4:
        return "human_core"
    if b <= 2 and h <= 2:
        return "low_both"
    return "other"


def bin_counts(bq, hq, mask):
    """5 x 5 counts of the cells in mask, indexed [b-1, h-1]."""
    out = np.zeros((5, 5), dtype=np.int64)
    np.add.at(out, (bq[mask] - 1, hq[mask] - 1), 1)
    return out


def bin_table(bq, hq, pos):
    n = bin_counts(bq, hq, np.ones(len(bq), bool))
    k = bin_counts(bq, hq, pos)
    total = k.sum()
    rows = []
    for b in range(1, 6):
        for h in range(1, 6):
            nc, npos = int(n[b - 1, h - 1]), int(k[b - 1, h - 1])
            rows.append({"b": b, "h": h, "region": region(b, h), "n_cells": nc, "n_pos": npos,
                         "rate": npos / nc if nc else None, "share": npos / total if total else None})
    return rows


def region_shares(bq, hq, mask):
    k = bin_counts(bq, hq, mask)
    total = k.sum()
    out = {r: 0 for r in REGIONS}
    for b in range(1, 6):
        for h in range(1, 6):
            out[region(b, h)] += int(k[b - 1, h - 1])
    return {r: v / total for r, v in out.items()}


def region_table(bq, hq, pos):
    n = bin_counts(bq, hq, np.ones(len(bq), bool))
    k = bin_counts(bq, hq, pos)
    out = {r: {"n_cells": 0, "n_pos": 0} for r in REGIONS}
    for b in range(1, 6):
        for h in range(1, 6):
            out[region(b, h)]["n_cells"] += int(n[b - 1, h - 1])
            out[region(b, h)]["n_pos"] += int(k[b - 1, h - 1])
    for v in out.values():
        v["rate"] = v["n_pos"] / v["n_cells"] if v["n_cells"] else None
        v["share"] = v["n_pos"] / k.sum()
        v["lift"] = v["rate"] / (k.sum() / n.sum()) if v["n_cells"] else None
    return out


def cliffs_delta(later, earlier):
    """P(later > earlier) - P(later < earlier); positive when the later year tends higher."""
    from scipy.stats import mannwhitneyu

    u = mannwhitneyu(later, earlier, alternative="two-sided").statistic
    return float(2 * u / (len(later) * len(earlier)) - 1)


def jsd(p, q):
    """Jensen-Shannon divergence (distance squared), base 2, of two count vectors."""
    from scipy.spatial.distance import jensenshannon

    p, q = np.asarray(p, float).ravel(), np.asarray(q, float).ravel()
    return float(jensenshannon(p / p.sum(), q / q.sum(), base=2) ** 2)


def summary(x):
    q1, m, q3 = np.quantile(x, [0.25, 0.5, 0.75])
    return {"n": int(len(x)), "q1": float(q1), "median": float(m), "q3": float(q3)}


def random_block_perm(blocks, rng):
    blocks = list(blocks)
    return dict(zip(blocks, [blocks[i] for i in rng.permutation(len(blocks))]))


def block_shuffle(ix, iy, pos, size, perm):
    """Move the positive cells of each size x size block to the block perm[block], keeping the offsets inside it.

    Positive cells that land where there is no prefecture cell are dropped."""
    index = np.full((iy.max() + 1, ix.max() + 1), -1, dtype=np.int64)
    index[iy, ix] = np.arange(len(ix))
    out = np.zeros(len(ix), bool)
    for j in np.flatnonzero(pos):
        bx, by = perm[(ix[j] // size, iy[j] // size)]
        nx, ny = bx * size + ix[j] % size, by * size + iy[j] % size
        if 0 <= ny < index.shape[0] and 0 <= nx < index.shape[1] and index[ny, nx] >= 0:
            out[index[ny, nx]] = True
    return out


def block_swap(a, b, block, swap):
    """Exchange the year labels a and b of every cell in the blocks with swap[block] True."""
    s = np.array([swap[k] for k in block])
    return np.where(s, b, a), np.where(s, a, b)


def block_flip(is_later, block, flip):
    """Flip the year label of every entry whose block (index into the sorted unique blocks) has flip True."""
    _, inv = np.unique(block, return_inverse=True)
    return np.asarray(is_later, bool) ^ np.asarray(flip, bool)[inv]


def pair_stats(pb, ph_, is_later, bq, hq):
    """Cliff's delta on both axes (later - earlier) and the JSD of the 25-bin compositions of two years' entries."""
    e, l_ = ~is_later, is_later
    ce = np.zeros((5, 5))
    cl = np.zeros((5, 5))
    np.add.at(ce, (bq[e] - 1, hq[e] - 1), 1)
    np.add.at(cl, (bq[l_] - 1, hq[l_] - 1), 1)
    return {"cliff_b": cliffs_delta(pb[l_], pb[e]), "cliff_h": cliffs_delta(ph_[l_], ph_[e]), "jsd": jsd(ce, cl)}
