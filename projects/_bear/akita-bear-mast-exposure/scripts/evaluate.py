"""Fit Mk on the training years, rank the cells of the target year, and score the ranking (capture@5% as the
bear project: metrics.rank_order with seed 0, the cell on the cut counted by its fraction)."""

import numpy as np

import metrics as mt
import model

MODELS = {"M1": "beech", "M2": "beech_mizunara", "M3": "mizunara", "M4": "konara", "M5": "beech_oak"}


def run(benv, e, s, counts, train, target, score_only=False):
    """benv: saved B_env surface for the target; e: exposure per cell; s: {year: mast scarcity}; counts: {year: reports}.
    The target year's counts are used only to score (never with score_only)."""
    off = model.logit(benv)
    fit = model.fit([(off, s[t] * e, counts[t] > 0) for t in train])
    sc = model.score(benv, e, fit["beta"], s[target])
    out = {"fit": fit, "s_target": s[target], "beta_times_s_target": fit["beta"] * s[target], "score": sc}
    if not score_only:
        out["metrics"] = metrics(sc, counts[target])
    return out


def metrics(score, c):
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = c > 0
    o = mt.rank_order(score)
    return {"capture@5%": mt.capture(o, y, 0.05), "capture@10%": mt.capture(o, y, 0.10),
            "capture@5%_reports": mt.capture(o, c, 0.05), "auc": float(roc_auc_score(y, score)),
            "ap": float(average_precision_score(y, score)), "n_pos": int(y.sum())}


def diff(score_a, score_b, c, blocks, k=0.05, weights_counts=False, B=1000, seed=0):
    """capture@k(a) - capture@k(b) and its 90% block-bootstrap interval (blocks resampled, cut redone each time)."""
    pos = c if weights_counts else (c > 0)
    oa, ob = mt.rank_order(score_a), mt.rank_order(score_b)
    point = mt.capture(oa, pos, k) - mt.capture(ob, pos, k)
    lo, hi, _ = mt.bootstrap_diff(oa, ob, pos, blocks, k, B=B, seed=seed)
    return {"diff": point, "lo90": lo, "hi90": hi}
