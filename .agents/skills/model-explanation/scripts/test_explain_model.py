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


def test_ice_shows_opposite_effects_that_the_average_hides():
    from explain_model import ice_curves

    rng = np.random.default_rng(5)
    X = rng.uniform(-1, 1, size=(1200, 2))
    y = 3 * X[:, 0] * np.sign(X[:, 1]) + rng.normal(scale=0.1, size=1200)
    grid, pd = partial_dependence(y, X, 0, "hgb", kfold(1200), "regression", points=7)
    curves, rows = ice_curves(y, X, 0, "hgb", kfold(1200), "regression", points=7, sample=200, seed=0)
    assert np.ptp(pd) < 1.0  # the average is nearly flat
    slopes = curves[:, -1] - curves[:, 0]
    up = X[rows, 1] > 0
    assert slopes[up].mean() > 3 and slopes[~up].mean() < -3


# Shapley values (interventional: a feature left out takes the background rows' values)

def test_shapley_values_of_a_two_player_game_by_hand():
    from explain_model import shapley_values

    f = lambda Z: Z[:, 0] * Z[:, 1]
    phi = shapley_values(f, np.array([[1.0, 1.0]]), np.array([[0.0, 0.0]]), [[0], [1]])
    assert phi.tolist() == [[0.5, 0.5]]  # v({}) 0, v({1}) 0, v({2}) 0, v({1,2}) 1: shared equally
    f = lambda Z: Z[:, 0] + 2 * Z[:, 1] * Z[:, 0]
    # v({}) 0, v({1}) 1, v({2}) 0, v({1,2}) 3: phi1 = (1 + 3) / 2 = 2, phi2 = (0 + 2) / 2 = 1
    assert shapley_values(f, np.array([[1.0, 1.0]]), np.array([[0.0, 0.0]]), [[0], [1]]).tolist() == [[2.0, 1.0]]


def test_shapley_values_of_a_linear_model_are_coefficient_times_distance_from_the_background_mean():
    rng = np.random.default_rng(3)
    beta = np.array([2.0, -1.0, 0.5, 0.0])
    f = lambda Z: Z @ beta + 7.0
    bg, x = rng.normal(size=(50, 4)), rng.normal(size=(10, 4))
    phi = shapley_values_of(f, x, bg)
    np.testing.assert_allclose(phi, beta * (x - bg.mean(0)), atol=1e-12)


def shapley_values_of(f, x, bg):
    from explain_model import shapley_values

    return shapley_values(f, x, bg, [[j] for j in range(x.shape[1])])


def test_shapley_values_add_up_to_the_prediction_minus_the_background_mean_and_an_unused_feature_gets_zero():
    rng = np.random.default_rng(4)
    f = lambda Z: np.sin(Z[:, 0]) * Z[:, 1] + np.maximum(Z[:, 2], 0)  # feature 3 unused
    bg, x = rng.normal(size=(40, 4)), rng.normal(size=(8, 4))
    phi = shapley_values_of(f, x, bg)
    np.testing.assert_allclose(phi.sum(1), f(x) - f(bg).mean(), atol=1e-12)
    assert np.abs(phi[:, 3]).max() < 1e-12


def test_a_group_is_one_player_with_the_sum_of_its_members_in_an_additive_model():
    from explain_model import shapley_values

    rng = np.random.default_rng(5)
    f = lambda Z: Z[:, 0] + Z[:, 1] + Z[:, 0] * Z[:, 2]
    bg, x = rng.normal(size=(30, 3)), rng.normal(size=(5, 3))
    grouped = shapley_values(f, x, bg, [[0, 1], [2]])
    np.testing.assert_allclose(grouped.sum(1), f(x) - f(bg).mean(), atol=1e-12)


def test_correlated_features_split_their_credit_unstably_and_the_pair_stays_put():
    # y depends on s; the model sees two noisy copies of s. Refitted on bootstrap samples, the linear model's
    # coefficients trade off between the copies and the share of the pair's Shapley value given to the first copy
    # jumps around (measured 0.55-0.94), while the pair's total barely moves (sd 0.7% of its mean). Boosting and
    # forests split less erratically here (0.67-0.77 and 0.65-0.80) but still not evenly.
    from explain_model import shap_summary

    rng = np.random.default_rng(6)
    s = rng.normal(size=600)
    X = np.c_[s + rng.normal(scale=0.05, size=600), s + rng.normal(scale=0.05, size=600), rng.normal(size=600)]
    y = s + rng.normal(scale=0.3, size=600)
    shares, totals = [], []
    for b in range(6):
        idx = np.random.default_rng(100 + b).integers(0, 600, 600)
        folds = {0: [(idx, np.arange(600))]}
        single = shap_summary(y, X, ["a", "b", "noise"], "linear", folds, "regression", explain=150, background=50)
        pair = shap_summary(y, X, ["a", "b", "noise"], "linear", folds, "regression", explain=150, background=50,
                            groups={"a+b": ["a", "b"]})
        shares.append(single["a"]["mean_abs"] / (single["a"]["mean_abs"] + single["b"]["mean_abs"]))
        totals.append(pair["a+b"]["mean_abs"])
    assert np.ptp(shares) > 0.2
    assert np.std(totals) / np.mean(totals) < 0.03


def test_shapley_values_are_taken_on_held_out_rows_with_a_training_background():
    from explain_model import shap_summary

    rng = np.random.default_rng(7)
    X = rng.normal(size=(300, 2))
    y = 2 * X[:, 0] + rng.normal(scale=0.5, size=300)
    r = shap_summary(y, X, ["x", "noise"], "linear", kfold(300), "regression", explain=60, background=40)
    assert r["x"]["mean_abs"] > 1.2 and r["noise"]["mean_abs"] < 0.1
    assert r["_check"]["max_efficiency_gap"] < 1e-8
    assert r["x"]["corr_with_value"] > 0.99  # the value rises with the feature
