"""uvx --with duckdb --with scikit-learn --with pytest pytest test_score_folds.py"""

import numpy as np
import pytest

from score_folds import predict_fold, run, score, simple_folds


def test_mean_median_group_mean_use_only_training_rows():
    ytr = np.array([1.0, 3.0, 11.0])
    Xtr, Xte = np.zeros((3, 1)), np.zeros((2, 1))
    assert predict_fold("mean", "regression", Xtr, ytr, Xte).tolist() == [5.0, 5.0]
    assert predict_fold("median", "regression", Xtr, ytr, Xte).tolist() == [3.0, 3.0]
    gtr = np.array(["a", "a", "b"])
    p = predict_fold("group_mean", "regression", Xtr, ytr, Xte, gtr, np.array(["a", "c"]))
    assert p.tolist() == [2.0, 5.0]  # group a mean; unseen group c -> overall mean


def test_score_values():
    s = score(np.array([0.0, 2.0]), np.array([1.0, 1.0]), "regression")
    assert s["rmse"] == 1.0 and s["mae"] == 1.0 and s["r2"] == pytest.approx(0.0)


def test_untested_rows_are_not_scored_and_n_counts_them():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    X = np.zeros((4, 1))
    folds = {0: [(np.array([0, 1]), np.array([2])), (np.array([0, 1, 2]), np.array([3]))]}
    r = run(y, X, None, ["mean"], folds, "regression")["mean"]
    assert r["n"] == [2]  # rows 0 and 1 are never tested
    # fold 1: mean(1,2)=1.5 vs 3 -> 1.5; fold 2: mean(1,2,3)=2 vs 4 -> 2
    assert r["rmse"][0] == pytest.approx(np.sqrt((1.5 ** 2 + 2 ** 2) / 2))


def test_a_row_tested_twice_in_one_repeat_is_refused():
    folds = {0: [(np.array([0]), np.array([1])), (np.array([0]), np.array([1]))]}
    with pytest.raises(SystemExit):
        run(np.array([1.0, 2.0]), np.zeros((2, 1)), None, ["mean"], folds, "regression")


def test_linear_recovers_a_line_and_group_mean_needs_a_group():
    X = np.arange(10, dtype=float).reshape(-1, 1)
    y = 2 * X[:, 0] + 1
    p = predict_fold("linear", "regression", X[:8], y[:8], X[8:])
    assert p == pytest.approx(y[8:])
    with pytest.raises(SystemExit):
        run(y, X, None, ["group_mean"], {0: [(np.arange(8), np.arange(8, 10))]}, "regression")


def test_simple_group_folds_never_split_a_group_and_cover_every_row_once():
    group = np.repeat(np.array(list("abcdefghij")), 3)
    for tr, te in simple_folds(30, "group", 5, group)[0]:
        assert not set(group[tr]) & set(group[te])
    tested = np.concatenate([te for _, te in simple_folds(30, "group", 5, group)[0]])
    assert sorted(tested.tolist()) == list(range(30))


def test_simple_row_folds_cover_every_row_once_per_repeat():
    f = simple_folds(23, "rows", 5, repeats=2)
    for r in f.values():
        assert sorted(np.concatenate([te for _, te in r]).tolist()) == list(range(23))
