import numpy as np

import transfer_eval as te


def test_block_folds_keep_each_block_in_one_fold_and_use_every_fold():
    blocks = np.repeat(np.arange(23), 7)
    f = te.block_folds(blocks, 5, seed=0)
    for b in np.unique(blocks):
        assert len(np.unique(f[blocks == b])) == 1
    assert set(np.unique(f)) == set(range(5))


def test_local_predictions_never_use_the_held_out_fold():
    rng = np.random.default_rng(0)
    n = 3000
    X = rng.random((n, 3)).astype(np.float32)
    y = rng.random(n) < 0.05
    blocks = np.repeat(np.arange(30), n // 30)
    p1 = te.local_cv(X, y, blocks, folds=5, seed=0, params={"max_iter": 20})
    # changing the labels of fold 0 must not change the predictions for fold 0
    f = te.block_folds(blocks, 5, seed=0)
    y2 = y.copy()
    y2[f == 0] = ~y2[f == 0]
    p2 = te.local_cv(X, y2, blocks, folds=5, seed=0, params={"max_iter": 20})
    np.testing.assert_allclose(p1[f == 0], p2[f == 0])
    assert not np.allclose(p1[f != 0], p2[f != 0])
