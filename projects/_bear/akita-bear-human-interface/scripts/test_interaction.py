"""Known-answer tests for the B x H meta-model inputs."""

import numpy as np
import pytest

import interface_interaction as ii


def test_block_folds_put_a_block_in_one_fold_and_spread_blocks_evenly():
    block = np.repeat(np.arange(10), 3)
    f = ii.block_folds(block, k=5, seed=0)
    for b in range(10):
        assert len(set(f[block == b])) == 1
    assert np.bincount(f[::3], minlength=5).tolist() == [2, 2, 2, 2, 2]


def test_design_centres_the_logits_and_adds_their_product_only_for_the_interaction():
    sb, sh = np.array([0.5, 0.5]), np.array([0.5, 0.5])
    d = ii.design(sb, sh, (0.0, 0.0), interaction=False)
    assert d.shape == (2, 2) and np.allclose(d, 0)
    d = ii.design(np.array([0.731058579]), np.array([0.268941421]), (0.0, 0.0), interaction=True)
    assert d[0].tolist() == pytest.approx([1.0, -1.0, -1.0], abs=1e-6)
