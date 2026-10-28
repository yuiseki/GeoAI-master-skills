import numpy as np

import run_matrix as rm


def test_subsample_keeps_all_positives_and_reweights_negatives():
    rng = np.random.default_rng(0)
    y = np.zeros(10000, dtype=bool)
    y[:50] = True
    keep, w = rm.subsample(y, rng)
    assert keep[:50].all()
    assert 800 < keep[50:].sum() < 1200
    # the weighted count of kept negatives estimates the true count
    assert abs((w[50:] * keep[50:]).sum() - 9950) < 1200
    assert (w[:50] == 1).all()


def test_variants_change_one_block_at_a_time():
    for name, (rep, drop, clim) in rm.VARIANTS.items():
        if name.startswith("combo_"):
            continue  # combinations are meant to change several blocks
        changed = len(rep) + (1 if drop else 0) + (1 if clim else 0)
        assert changed <= 1, name
