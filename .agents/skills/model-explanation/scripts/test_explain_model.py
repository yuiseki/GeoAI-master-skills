"""uvx --with duckdb --with scikit-learn --with pytest pytest test_explain_model.py"""

import numpy as np
from sklearn.model_selection import KFold

from explain_model import partial_dependence, permutation_importance


def kfold(n, k=5, repeats=(0,)):
    return {r: list(KFold(k, shuffle=True, random_state=r).split(np.zeros(n))) for r in repeats}


def test_only_the_feature_the_target_depends_on_matters():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 2))
    y = 3 * X[:, 0] + rng.normal(scale=0.5, size=600)
    imp = permutation_importance(y, X, ["x", "noise"], "linear", kfold(600), "regression")
    assert imp["x"]["mean"] > 1.0
    assert abs(imp["noise"]["mean"]) < 0.02


def test_importance_is_measured_on_held_out_rows():
    # A random forest memorises a pure-noise feature on its training rows; on held-out rows
    # permuting that feature costs nothing.
    rng = np.random.default_rng(1)
    X = rng.normal(size=(400, 2))
    y = X[:, 0] + rng.normal(scale=1.0, size=400)
    imp = permutation_importance(y, X, ["x", "noise"], "rf", kfold(400), "regression")
    assert abs(imp["noise"]["mean"]) < 0.03


def test_permuting_correlated_features_together_shows_their_joint_weight():
    rng = np.random.default_rng(2)
    s = rng.normal(size=800)
    X = np.c_[s + rng.normal(scale=0.1, size=800), s + rng.normal(scale=0.1, size=800)]
    y = s + rng.normal(scale=0.3, size=800)
    imp = permutation_importance(y, X, ["a", "b"], "linear", kfold(800), "regression",
                                 groups={"a+b": ["a", "b"]})
    single = max(imp["a"]["mean"], imp["b"]["mean"])
    assert imp["a+b"]["mean"] > 1.5 * single
    # Shuffled together, a and b stay paired, so the permuted prediction keeps its full spread and
    # R2 falls by about 0.92 + 0.92 = 1.83. Shuffled one by one, the two halves of the prediction
    # partly cancel and the fall is only about 1.38.
    assert imp["a+b"]["mean"] > 1.6


def test_partial_dependence_follows_the_shape_of_the_relation():
    rng = np.random.default_rng(3)
    X = rng.uniform(-2, 2, size=(800, 2))
    y = X[:, 0] ** 2 + rng.normal(scale=0.1, size=800)
    grid, pd = partial_dependence(y, X, 0, "hgb", kfold(800), "regression", points=9)
    centre = pd[len(pd) // 2]
    assert pd[0] > centre + 2 and pd[-1] > centre + 2
    assert grid[0] < -1.5 and grid[-1] > 1.5
