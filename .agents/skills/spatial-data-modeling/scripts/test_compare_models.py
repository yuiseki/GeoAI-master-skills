"""uvx --with duckdb --with scikit-learn --with pytest pytest test_compare_models.py

Add --with tabpfn==9.1.0 to run the TabPFN tests too; without it they are skipped.
"""

import numpy as np
import pytest
from sklearn.base import BaseEstimator, RegressorMixin

from compare_models import MODELS, TABPFN_V2_WEIGHTS, make_splits, oof_predict, run

OPTIONAL = {"tabpfn_v2"}


class Memoriser(BaseEstimator, RegressorMixin):
    """Returns the training target of an identical row, 0 for an unseen row."""

    def fit(self, X, y):
        self.table_ = {tuple(x): t for x, t in zip(X, y)}
        return self

    def predict(self, X):
        return np.array([self.table_.get(tuple(x), 0.0) for x in X])


def test_each_row_is_predicted_by_a_model_that_did_not_see_it():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(100, 2))
    y = rng.normal(size=100)
    splits = make_splits(X, y, None, folds=5, group_folds=False, seed=0, task="regression")
    pred = oof_predict(Memoriser, X, y, splits, task="regression")
    # A leak would let the memoriser return y itself.
    assert np.allclose(pred, 0.0)


def test_group_folds_hold_out_whole_groups():
    X = np.zeros((40, 1))
    y = np.arange(40, dtype=float)
    group = np.array([f"g{i // 4}" for i in range(40)])
    for train, test in make_splits(X, y, group, folds=5, group_folds=True, seed=0, task="regression"):
        assert not set(group[train]) & set(group[test])


def test_trees_beat_linear_on_a_step_and_linear_wins_on_a_line():
    rng = np.random.default_rng(1)
    x = rng.uniform(-1, 1, size=400)
    X = np.c_[x, rng.normal(size=400)]
    step = (x > 0).astype(float) + rng.normal(scale=0.1, size=400)
    line = 2 * x + rng.normal(scale=0.1, size=400)
    names = ["linear", "rf", "hgb"]
    s = run(step, X, None, names, folds=5, group_folds=False, seeds=[0], task="regression")
    assert s["rf"]["r2"][0] > s["linear"]["r2"][0] + 0.1
    assert s["hgb"]["r2"][0] > s["linear"]["r2"][0] + 0.1
    s = run(line, X, None, names, folds=5, group_folds=False, seeds=[0], task="regression")
    assert s["linear"]["r2"][0] >= s["rf"]["r2"][0]


def test_classification_scores_a_prior_baseline_at_its_entropy():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(500, 1))
    y = (rng.uniform(size=500) < 0.3).astype(int)  # unrelated to X
    s = run(y, X, None, ["prior", "linear"], folds=5, group_folds=False, seeds=[0],
            task="classification")
    p = y.mean()
    entropy = -(p * np.log(p) + (1 - p) * np.log(1 - p))
    assert s["prior"]["log_loss"][0] == pytest.approx(entropy, abs=0.01)
    assert s["linear"]["auc"][0] < 0.6


def test_every_model_name_runs_for_both_tasks():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(120, 2))
    group = np.array([f"g{i % 6}" for i in range(120)])
    yr = X[:, 0] + rng.normal(size=120)
    yc = (yr > 0).astype(int)
    for task, y in (("regression", yr), ("classification", yc)):
        names = [n for n, m in MODELS.items() if task in m and n not in OPTIONAL]
        s = run(y, X, group, names, folds=3, group_folds=True, seeds=[0, 1], task=task)
        assert set(s) == set(names)


def test_tabpfn_uses_the_pinned_v2_weights():
    pytest.importorskip("tabpfn")
    for task, (repo, filename, revision) in TABPFN_V2_WEIGHTS.items():
        model = MODELS["tabpfn_v2"][task](0)
        path = str(model.model_path)
        assert path.endswith(filename)
        assert f"snapshots/{revision}/" in path
        assert filename.startswith("tabpfn-v2-")


def test_tabpfn_runs_out_of_fold():
    pytest.importorskip("tabpfn")
    rng = np.random.default_rng(4)
    X = rng.normal(size=(60, 2))
    y = 2 * X[:, 0] + rng.normal(scale=0.1, size=60)
    s = run(y, X, None, ["mean", "tabpfn_v2"], folds=3, group_folds=False, seeds=[0],
            task="regression")
    assert s["tabpfn_v2"]["r2"][0] > s["mean"]["r2"][0] + 0.5
