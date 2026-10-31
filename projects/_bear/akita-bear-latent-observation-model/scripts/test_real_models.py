"""Known-answer tests for the cross-source validation helpers."""

import numpy as np
import pytest

import real_models as rm


def test_folds_keep_a_block_together_and_balance_blocks():
    blocks = np.repeat([f"{i:06d}" for i in range(10)], 3)
    f = rm.folds(blocks, k=5, seed=0)
    for b in np.unique(blocks):
        assert len(set(f[blocks == b])) == 1
    assert sorted(np.bincount(f[::3]).tolist()) == [2, 2, 2, 2, 2]


def test_shuffle_env_moves_whole_blocks_and_masks_targets_without_a_source():
    codes = np.array(["11111122", "11111127", "22222222"])
    data = {"mesh_code": codes, "E": np.array([[1, 0, 1], [1, 1, 0]]), "env_mask": np.ones((2, 3), bool)}
    for seed in range(20):
        E, mask = rm.shuffle_env(data, seed)
        if mask[:, 2].all() and not mask[:, 1].any():  # 111111 <-> 222222: position 27 has no source
            assert E[:, 2].tolist() == [1, 1]
            break
    else:
        pytest.fail("no seed swapped the two blocks")


def test_block_boot_sums_and_brackets_the_total():
    diff = np.array([1.0, 1.0, -0.5, 2.0])
    tot, lo, hi = rm.block_boot(diff, np.array(["a", "a", "b", "c"]), B=500)
    assert tot == 3.5 and lo <= tot <= hi


def test_logmeanexp_is_stable():
    assert rm.logmeanexp(np.array([-1000.0, -1000.0])) == pytest.approx(-1000.0)
