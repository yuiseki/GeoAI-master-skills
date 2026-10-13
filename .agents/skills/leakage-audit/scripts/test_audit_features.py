"""uvx --with duckdb --with scikit-learn --with pytest pytest test_audit_features.py"""

import numpy as np
from sklearn.model_selection import KFold

from audit_features import audit


def kfold(n, k=5, repeats=(0,)):
    return {r: list(KFold(k, shuffle=True, random_state=r).split(np.zeros(n))) for r in repeats}


def make(n=300, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = x + rng.normal(scale=1.0, size=n)
    return rng, x, y


def test_a_restatement_of_the_target_is_flagged():
    rng, x, y = make()
    restated = y + rng.normal(scale=0.05, size=len(y))  # e.g. male life expectancy for life expectancy
    X = np.c_[x, restated]
    r = audit(y, X, ["x", "restated"], None, kfold(len(y)), "regression", flag_score=0.9)
    flagged = {f["feature"] for f in r["single_feature"] if f["flag"]}
    assert flagged == {"restated"}


def test_a_feature_that_identifies_the_group_is_flagged():
    rng = np.random.default_rng(1)
    group = np.array([f"g{i % 30}" for i in range(300)])
    code = np.array([float(i % 30) for i in range(300)])  # constant within a group, unique across
    X = np.c_[rng.normal(size=300), code]
    y = rng.normal(size=300)
    r = audit(y, X, ["noise", "code"], group, kfold(300), "regression")
    ident = {f["feature"]: f["flag"] for f in r["identifies_group"]}
    assert ident == {"noise": False, "code": True}


def test_permuted_target_scores_nothing_with_an_honest_pipeline():
    _, x, y = make()
    r = audit(y, x[:, None], ["x"], None, kfold(len(y)), "regression")
    assert r["permuted"]["r2"] < 0.05
    assert r["real"]["r2"] > 0.3


def test_identical_feature_rows_across_train_and_test_are_counted():
    rng = np.random.default_rng(2)
    base = rng.normal(size=(50, 2))
    X = np.r_[base, base]  # every row has a twin
    y = rng.normal(size=100)
    folds = kfold(100)
    r = audit(y, X, ["a", "b"], None, folds, "regression")
    assert r["duplicates"]["test_rows_with_a_train_twin"] > 0
    unique = rng.normal(size=(100, 2))
    r = audit(y, unique, ["a", "b"], None, folds, "regression")
    assert r["duplicates"]["test_rows_with_a_train_twin"] == 0
