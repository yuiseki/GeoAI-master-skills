"""Contracts for one fixed 10km-block, 5-fold same-year diagnostic."""

import numpy as np
import pytest

import model_eval as me
import same_year_spatial_oof as audit


def test_block_folds_are_label_free_and_complete():
    ix = np.repeat(np.arange(10) * 100, 4)
    iy = np.tile(np.array([0, 1, 100, 101]), 10)
    blocks, fold = audit.fixed_folds(ix, iy)
    assert len(np.unique(blocks)) == 20
    assert set(fold) == set(range(5))
    for block in np.unique(blocks):
        assert len(np.unique(fold[blocks == block])) == 1
    for f in range(5):
        assert np.count_nonzero(fold == f) == 8


def test_oof_fits_only_other_blocks_and_predicts_every_cell_once():
    ix = np.repeat(np.arange(10) * 100, 4)
    iy = np.tile(np.array([0, 1, 100, 101]), 10)
    blocks, fold = audit.fixed_folds(ix, iy)
    X = np.arange(len(ix), dtype=np.float32).reshape(-1, 1)
    y = (np.arange(len(ix)) % 3 == 0)
    calls = []

    class FakeModel:
        def fit(self, x, target):
            calls.append((x[:, 0].astype(int).copy(), target.copy()))
            return self

        def predict_proba(self, x):
            return np.column_stack((np.zeros(len(x)), x[:, 0] / len(X)))

    score, diagnostics = audit.oof_scores(X, y, blocks, fold, model_factory=FakeModel)
    np.testing.assert_allclose(score, np.arange(len(X)) / len(X))
    assert len(calls) == 5
    for f, (seen, target) in enumerate(calls):
        assert not np.isin(blocks[seen], blocks[fold == f]).any()
        np.testing.assert_array_equal(target, y[seen])
    assert sum(row["n_test"] for row in diagnostics) == len(X)


def test_invalid_split_or_label_is_rejected():
    ix = np.repeat(np.arange(10) * 100, 4)
    iy = np.tile(np.array([0, 1, 100, 101]), 10)
    blocks, fold = audit.fixed_folds(ix, iy)
    X = np.ones((len(ix), 1), dtype=np.float32)
    y = np.arange(len(ix)) % 2 == 0
    bad = fold.copy()
    bad[0] = (bad[0] + 1) % 5
    with pytest.raises(ValueError, match="block"):
        audit.oof_scores(X, y, blocks, bad)
    with pytest.raises(ValueError, match="binary"):
        audit.oof_scores(X, y.astype(int), blocks, fold)


def test_oof_scoring_uses_existing_capture_and_tie_breaking():
    score = np.array([0.1, 0.7, 0.7, 0.2, 0.9] * 20)
    positive = np.array([False, True, False, False, True] * 20)
    expected = me.evaluate({"B_env": score}, positive, positive.astype(int),
                           np.empty(0), [], B=0, seed=0)["B_env"]
    actual = audit.score_metrics(score, positive)
    assert all(actual[key] == expected[key] for key in audit.METRICS)
