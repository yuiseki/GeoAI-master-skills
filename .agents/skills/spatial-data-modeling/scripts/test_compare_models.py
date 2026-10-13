"""uvx --with duckdb --with scikit-learn --with pytest pytest test_compare_models.py

Add --with tabpfn==9.1.0 to run the TabPFN tests too; without it they are skipped.
"""

import duckdb
import numpy as np
import pytest
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold

from compare_models import MODELS, TABPFN_V2_WEIGHTS, load_folds, oof_predict, run

OPTIONAL = {"tabpfn_v2"}


def kfold(n, k=5, repeats=(0,), y=None):
    """Folds in the shape load_folds returns, for tests."""
    out = {}
    for r in repeats:
        if y is not None:
            out[r] = list(StratifiedKFold(k, shuffle=True, random_state=r).split(np.zeros(n), y))
        else:
            out[r] = list(KFold(k, shuffle=True, random_state=r).split(np.zeros(n)))
    return out


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
    pred = oof_predict(Memoriser, X, y, kfold(100)[0], task="regression")
    # A leak would let the memoriser return y itself.
    assert np.allclose(pred, 0.0)


def test_group_mean_uses_training_rows_only():
    # Every group has one row whose target is unrelated to the other. If the group mean were
    # taken over all rows, it would contain each test row's own target and look good.
    rng = np.random.default_rng(1)
    group = np.array([f"g{i}" for i in range(100) for _ in range(2)])
    y = rng.normal(size=200)
    s = run(y, np.zeros((200, 1)), group, ["group_mean"], kfold(200, k=2), "regression")
    assert s["group_mean"]["r2"][0] < 0.1


def test_group_mean_predicts_a_seen_group_by_its_training_mean():
    rng = np.random.default_rng(6)
    group = np.array([f"g{i % 10}" for i in range(300)])
    y = 10.0 * (np.arange(300) % 10) + rng.normal(size=300)
    s = run(y, np.zeros((300, 1)), group, ["mean", "group_mean"], kfold(300), "regression")
    assert s["group_mean"]["r2"][0] > 0.95
    assert s["mean"]["r2"][0] < 0.05


def test_group_mean_falls_back_to_the_mean_when_whole_groups_are_held_out():
    rng = np.random.default_rng(5)
    group = np.array([f"g{i % 20}" for i in range(200)])
    y = rng.normal(size=200) + (np.arange(200) % 20)
    folds = {0: list(GroupKFold(5).split(np.zeros(200), groups=group))}
    s = run(y, np.zeros((200, 1)), group, ["mean", "group_mean"], folds, "regression")
    assert s["group_mean"]["r2"][0] == pytest.approx(s["mean"]["r2"][0], abs=1e-9)


def test_trees_beat_linear_on_a_step_and_linear_wins_on_a_line():
    rng = np.random.default_rng(1)
    x = rng.uniform(-1, 1, size=400)
    X = np.c_[x, rng.normal(size=400)]
    step = (x > 0).astype(float) + rng.normal(scale=0.1, size=400)
    line = 2 * x + rng.normal(scale=0.1, size=400)
    names = ["linear", "rf", "hgb"]
    s = run(step, X, None, names, kfold(400), "regression")
    assert s["rf"]["r2"][0] > s["linear"]["r2"][0] + 0.1
    assert s["hgb"]["r2"][0] > s["linear"]["r2"][0] + 0.1
    s = run(line, X, None, names, kfold(400), "regression")
    assert s["linear"]["r2"][0] >= s["rf"]["r2"][0]


def test_classification_scores_a_prior_baseline_at_its_entropy():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(500, 1))
    y = (rng.uniform(size=500) < 0.3).astype(int)  # unrelated to X
    s = run(y, X, None, ["prior", "linear"], kfold(500, y=y), "classification")
    p = y.mean()
    entropy = -(p * np.log(p) + (1 - p) * np.log(1 - p))
    assert s["prior"]["log_loss"][0] == pytest.approx(entropy, abs=0.01)
    assert s["linear"]["auc"][0] < 0.6


def test_rows_no_fold_tests_are_left_out_of_the_score():
    y = np.arange(10, dtype=float)
    X = y[:, None]
    folds = {0: [(np.arange(0, 6), np.arange(6, 8)), (np.arange(0, 8), np.arange(8, 10))]}
    s = run(y, X, None, ["mean"], folds, "regression")
    assert s["mean"]["n"] == [4]
    # mean of rows 0-5 is 2.5 for rows 6, 7; mean of rows 0-7 is 3.5 for rows 8, 9
    err = np.array([6 - 2.5, 7 - 2.5, 8 - 3.5, 9 - 3.5])
    assert s["mean"]["rmse"][0] == pytest.approx(np.sqrt((err ** 2).mean()))


def test_a_row_tested_twice_in_one_repeat_stops_the_run():
    y = np.arange(6, dtype=float)
    folds = {0: [(np.arange(0, 3), np.arange(3, 6)), (np.arange(0, 2), np.arange(2, 4))]}
    with pytest.raises(SystemExit):
        run(y, y[:, None], None, ["mean"], folds, "regression")


def test_load_folds_maps_ids_and_refuses_unknown_ids(tmp_path):
    path = tmp_path / "folds.parquet"
    duckdb.sql(f"""
        copy (select * from (values (0, 0, 'a', 'train'), (0, 0, 'b', 'test'),
                                    (0, 1, 'b', 'train'), (0, 1, 'a', 'test'))
              t(repeat, fold, id, role)) to '{path}' (format parquet)
    """)
    folds = load_folds(str(path), np.array(["b", "a", "c"]))
    (train0, test0), (train1, test1) = folds[0]
    assert train0.tolist() == [1] and test0.tolist() == [0]
    assert train1.tolist() == [0] and test1.tolist() == [1]
    with pytest.raises(SystemExit):
        load_folds(str(path), np.array(["a"]))


def test_every_model_name_runs_for_both_tasks():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(120, 2))
    group = np.array([f"g{i % 6}" for i in range(120)])
    yr = X[:, 0] + rng.normal(size=120)
    yc = (yr > 0).astype(int)
    for task, y in (("regression", yr), ("classification", yc)):
        names = [n for n, m in MODELS.items() if task in m and n not in OPTIONAL]
        s = run(y, X, group, names, kfold(120, k=3, repeats=(0, 1)), task)
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
    s = run(y, X, None, ["mean", "tabpfn_v2"], kfold(60, k=3), "regression")
    assert s["tabpfn_v2"]["r2"][0] > s["mean"]["r2"][0] + 0.5
