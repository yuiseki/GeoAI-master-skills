"""uvx --with duckdb --with scikit-learn --with pytest pytest test_compare_models.py

Add --with tabpfn==9.1.0 to run the TabPFN tests too; without it they are skipped.
"""

import duckdb
import numpy as np
import pytest
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold

from compare_models import MODELS, TABPFN_V2_WEIGHTS, load_folds, oof_predict, run, score

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


def test_predictions_are_kept_for_every_tested_row_only():
    y = np.arange(10, dtype=float)
    folds = {0: [(np.arange(0, 6), np.arange(6, 8)), (np.arange(0, 8), np.arange(8, 10))]}
    preds = []
    run(y, y[:, None], None, ["mean"], folds, "regression", preds)
    assert sorted((r, m, i) for r, m, i, _ in preds) == [(0, "mean", i) for i in range(6, 10)]
    assert dict((i, v) for _, _, i, v in preds) == {6: 2.5, 7: 2.5, 8: 3.5, 9: 3.5}


def test_weighted_mean_baseline_and_weighted_scores():
    from sklearn.metrics import r2_score

    y = np.array([0.0, 0.0, 10.0, 10.0, 0.0, 10.0])
    w = np.array([1.0, 1.0, 3.0, 3.0, 1.0, 3.0])
    folds = {0: [(np.array([0, 1, 2, 3]), np.array([4, 5]))]}
    preds = []
    s = run(y, np.zeros((6, 1)), None, ["mean"], folds, "regression", preds, weights=w)
    # Training rows 0-3: weighted mean (0 + 0 + 30 + 30) / 8 = 7.5.
    assert {i: v for _, _, i, v in preds} == {4: 7.5, 5: 7.5}
    assert s["mean"]["r2"][0] == pytest.approx(r2_score(y[4:], [7.5, 7.5], sample_weight=w[4:]))


def test_weights_reach_the_model_fit():
    # Heavily weighted rows follow y = x; lightly weighted rows are wild. A weighted linear fit
    # follows the heavy rows and scores far better on them than an unweighted one.
    rng = np.random.default_rng(7)
    x = rng.uniform(-1, 1, 400)
    heavy = np.arange(400) % 4 != 0
    y = np.where(heavy, x, rng.normal(scale=20, size=400))
    w = np.where(heavy, 1.0, 0.0001)
    weighted = run(y, x[:, None], None, ["linear"], kfold(400), "regression", weights=w)
    # Scored with the weights, only a fit that also used them follows the heavy rows.
    assert weighted["linear"]["r2"][0] > 0.9


def test_a_model_without_sample_weight_support_stops_the_run():
    from sklearn.neighbors import KNeighborsRegressor

    MODELS["knn_no_weights"] = {"regression": lambda seed: KNeighborsRegressor(3)}
    try:
        y = np.arange(20, dtype=float)
        with pytest.raises(SystemExit):
            run(y, y[:, None], None, ["knn_no_weights"], kfold(20, k=2), "regression",
                weights=np.ones(20))
    finally:
        del MODELS["knn_no_weights"]


def test_effective_sample_size_of_weights():
    from compare_models import effective_n

    assert effective_n(np.ones(10)) == pytest.approx(10)
    assert effective_n(np.r_[np.ones(9), 0.0]) == pytest.approx(9)
    assert effective_n(np.r_[100.0, np.ones(99)]) == pytest.approx(199 ** 2 / (100 ** 2 + 99))


# Multiclass. 100 rows: 90 of class 0, 9 of class 1, 1 of class 2; counts worked out by hand.
Y3 = np.array([0] * 90 + [1] * 9 + [2])


def probs(predicted):
    """0.8 on the predicted class, 0.1 on each of the other two."""
    p = np.full((len(predicted), 3), 0.1)
    p[np.arange(len(predicted)), predicted] = 0.8
    return p


def test_majority_prediction_looks_accurate_but_macro_f1_shows_the_failure():
    s = score(Y3, np.tile([0.9, 0.09, 0.01], (100, 1)), "classification")
    assert s["accuracy"] == pytest.approx(0.90)
    assert s["balanced_accuracy"] == pytest.approx(1 / 3)
    assert s["macro_f1"] == pytest.approx((180 / 190) / 3)  # class 0: P 0.9, R 1; classes 1 and 2: 0
    assert s["weighted_f1"] == pytest.approx(0.9 * 180 / 190)
    assert s["log_loss"] == pytest.approx(-(0.9 * np.log(0.9) + 0.09 * np.log(0.09) + 0.01 * np.log(0.01)))
    assert s["recall[2]"] == 0 and s["f1[2]"] == 0


def test_accuracy_picks_the_model_that_never_finds_the_rare_class_and_macro_f1_does_not():
    # A: all of class 0, 5 of 9 of class 1, never class 2. B: 85 of 90, 7 of 9, and the one row of class 2.
    a = np.array([0] * 90 + [1] * 5 + [0] * 4 + [0])
    b = np.array([0] * 85 + [1] * 5 + [1] * 7 + [0] * 2 + [2])
    sa, sb = score(Y3, probs(a), "classification"), score(Y3, probs(b), "classification")
    assert (sa["accuracy"], sb["accuracy"]) == (pytest.approx(0.95), pytest.approx(0.93))
    assert sa["macro_f1"] == pytest.approx((180 / 185 + 10 / 14 + 0) / 3)
    assert sb["macro_f1"] == pytest.approx((170 / 177 + 14 / 21 + 1) / 3)
    assert sa["balanced_accuracy"] == pytest.approx((1 + 5 / 9 + 0) / 3)
    assert sb["balanced_accuracy"] == pytest.approx((85 / 90 + 7 / 9 + 1) / 3)
    assert sa["accuracy"] > sb["accuracy"] and sa["macro_f1"] < sb["macro_f1"]
    assert sa["precision[1]"] == 1 and sb["precision[1]"] == pytest.approx(7 / 12)


def test_multiclass_run_scores_the_prior_at_its_entropy_and_keeps_class_labels():
    rng = np.random.default_rng(4)
    X = rng.normal(size=(600, 2))
    y = np.array(["forest", "urban", "water"])[np.argmax(X @ [[3, -3, 0], [0, 3, -3]] + rng.gumbel(size=(600, 3)), 1)]
    s = run(y, X, None, ["prior", "linear"], kfold(600, y=y), "classification")
    share = np.unique(y, return_counts=True)[1] / 600
    assert s["prior"]["log_loss"][0] == pytest.approx(-(share * np.log(share)).sum(), abs=0.01)
    assert s["linear"]["log_loss"][0] < s["prior"]["log_loss"][0] - 0.3
    assert {"recall[forest]", "recall[urban]", "recall[water]", "macro_f1"} <= set(s["linear"])


def test_a_class_missing_from_a_training_fold_still_gets_its_own_column():
    # the single row of class 1 is not in the training rows of the fold that tests it; there the model
    # knows classes 0 and 2 only, and class 2's probability must still land in column 2
    y = np.array([0] * 90 + [1] + [2] * 9)
    X = np.r_[np.zeros((90, 1)), np.ones((1, 1)), np.full((9, 1), 2.0)]
    s = run(y, X, None, ["prior", "rf"], kfold(100, k=4), "classification")
    assert s["rf"]["recall[1]"][0] == 0
    assert s["rf"]["recall[2]"][0] == 1
    assert np.isfinite(s["rf"]["log_loss"][0])


def test_multiclass_predictions_are_one_probability_per_class():
    preds = []
    X = np.random.default_rng(5).normal(size=(100, 1))
    run(Y3, X, None, ["prior"], kfold(100, k=4, y=Y3 > 0), "classification", predictions=preds)
    assert len(preds) == 300  # 100 rows x 3 classes
    assert {p[2] for p in preds} == set(range(100))


def _time_folds(time, periods=(7, 8, 9)):
    return {0: [(np.flatnonzero(time < p), np.flatnonzero(time == p)) for p in periods]}


def test_inner_splits_are_the_other_folds_inside_the_training_rows():
    from compare_models import inner_splits

    group = np.repeat(np.arange(10), 6)
    splits = list(GroupKFold(5).split(np.zeros(60), groups=group))
    for k, (train, test) in enumerate(splits):
        inner = inner_splits(splits, k)
        assert len(inner) == 4
        for itrain, ival in inner:
            rows_train, rows_val = train[itrain], train[ival]  # positions within the training rows
            assert not set(rows_train) & set(test) and not set(rows_val) & set(test)
            assert not set(group[rows_train]) & set(group[rows_val])  # whole groups held out inside too
        assert sorted(np.concatenate([train[v] for _, v in inner])) == sorted(train)


def test_inner_splits_of_time_folds_look_only_backwards():
    from compare_models import inner_splits, time_inner_splits

    time = np.repeat(np.arange(10), 5)
    splits = _time_folds(time)[0]
    assert inner_splits(splits, 0) == []  # the first test period has no earlier fold to tune on
    for itrain, ival in inner_splits(splits, 2):
        assert time[splits[2][0][itrain]].max() < time[splits[2][0][ival]].min()
    inner = time_inner_splits(time[splits[0][0]], folds=3)
    assert len(inner) == 3
    for itrain, ival in inner:
        assert time[splits[0][0][itrain]].max() < time[splits[0][0][ival]].min()
        assert len(set(time[splits[0][0][ival]])) == 1


def _grouped_world(seed=0, groups=40, per=15):
    # Each group has its own feature vector and its own level of the target, unrelated to each
    # other: the features identify the group but say nothing about a new group's level.
    rng = np.random.default_rng(seed)
    g = np.repeat(np.arange(groups), per)
    X = rng.normal(size=(groups, 8))[g] + 0.1 * rng.normal(size=(groups * per, 8))
    y = 3 * rng.normal(size=groups)[g] + rng.normal(size=groups * per)
    return X, y, g


def test_ridge_tuned_on_held_out_groups_chooses_a_larger_penalty_than_on_shuffled_rows():
    X, y, g = _grouped_world()
    search = MODELS["ridge"]["regression"](0)
    grouped = list(GroupKFold(4).split(X, groups=g))
    shuffled = list(KFold(4, shuffle=True, random_state=0).split(X))
    a_grouped = search.fit(X, y, inner=grouped).best_param_
    a_shuffled = MODELS["ridge"]["regression"](0).fit(X, y, inner=shuffled).best_param_
    assert a_grouped == max(search.grid)  # the features say nothing about a new group's level
    assert a_grouped > 10 * a_shuffled


def test_boosting_stops_earlier_when_tuned_on_held_out_groups():
    X, y, g = _grouped_world(seed=1)
    grouped = list(GroupKFold(4).split(X, groups=g))
    shuffled = list(KFold(4, shuffle=True, random_state=0).split(X))
    n_grouped = MODELS["hgb"]["regression"](0).fit(X, y, inner=grouped).best_param_
    n_shuffled = MODELS["hgb"]["regression"](0).fit(X, y, inner=shuffled).best_param_
    assert n_grouped < n_shuffled / 2


class Recorder(BaseEstimator, RegressorMixin):
    """Remembers every row it was fitted on (by its first feature, the row number)."""

    seen = []

    def __init__(self, alpha=1.0):
        self.alpha = alpha

    def fit(self, X, y, sample_weight=None):
        Recorder.seen.append(set(X[:, 0].astype(int)))
        return self

    def predict(self, X):
        return np.full(len(X), self.alpha)


def test_the_search_fits_its_candidates_on_inner_training_rows_only():
    from compare_models import InnerSearch

    Recorder.seen = []
    X = np.c_[np.arange(40), np.zeros(40)]
    y = np.full(40, 2.0)
    inner = list(KFold(4).split(X))
    search = InnerSearch(lambda a: Recorder(a), [0.0, 2.0, 5.0], "regression").fit(X, y, inner=inner)
    assert search.best_param_ == 2.0
    for (train, _), seen in zip(inner * 3, Recorder.seen[:12]):
        assert seen == set(train)
    assert Recorder.seen[-1] == set(range(40))  # refitted on all the training rows at the end


def test_standardising_happens_inside_each_candidate():
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    for task in ("regression", "classification"):
        search = MODELS["ridge"][task](0)
        candidate = search.make(search.grid[0])
        assert isinstance(candidate, Pipeline) and isinstance(candidate.steps[0][1], StandardScaler)


def test_tuned_models_need_inner_folds_and_time_folds_can_supply_them():
    rng = np.random.default_rng(8)
    time = np.repeat(np.arange(10), 20)
    X = rng.normal(size=(200, 2))
    y = X[:, 0] + rng.normal(size=200)
    with pytest.raises(SystemExit, match="inner-time"):
        run(y, X, None, ["ridge"], _time_folds(time), "regression")
    s = run(y, X, None, ["ridge", "hgb"], _time_folds(time), "regression", inner_time=time)
    assert s["ridge"]["n"] == [60]


def test_tuned_classifiers_run_with_a_class_missing_from_an_inner_fold():
    rng = np.random.default_rng(9)
    X = rng.normal(size=(90, 2))
    y = np.r_[np.zeros(40, int), np.ones(40, int), np.full(10, 2)]
    s = run(y, X, None, ["ridge", "hgb"], kfold(90, k=3), "classification")
    assert np.isfinite(s["ridge"]["log_loss"][0]) and np.isfinite(s["hgb"]["log_loss"][0])
