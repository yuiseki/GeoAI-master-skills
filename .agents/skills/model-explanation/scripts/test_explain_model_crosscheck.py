"""uvx --with shap --with duckdb --with scikit-learn --with pytest pytest test_explain_model_crosscheck.py

Shapley values against the shap package (0.53.0): its exact explainer with an independent (interventional)
masker over the same background rows, and its TreeExplainer with feature_perturbation="interventional", which
computes the same quantity by walking the trees instead of enumerating subsets.

TreeExplainer is not used on HistGradientBoostingRegressor: with scikit-learn 1.9.1 its own values do not add up
to the model's output (off by 0.14 on this data, and it raises its additivity error), while on
GradientBoostingRegressor and random forests they agree with ours to 1e-7.
"""

import numpy as np
import pytest

from explain_model import shapley_values

shap = pytest.importorskip("shap")


def _data(seed=0, n=300):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 5))
    X[:, 1] = 0.7 * X[:, 0] + 0.3 * X[:, 1]  # a correlated pair
    y = np.sin(X[:, 0]) + X[:, 1] * X[:, 2] + 0.5 * (X[:, 3] > 0) + rng.normal(scale=0.2, size=n)
    return X, y


def test_exact_shapley_values_match_shaps_exact_explainer():
    from sklearn.neural_network import MLPRegressor

    X, y = _data()
    m = MLPRegressor(hidden_layer_sizes=(16,), max_iter=2000, random_state=0).fit(X, y)
    bg, ex = X[:40], X[200:230]
    ours = shapley_values(m.predict, ex, bg, [[j] for j in range(5)])
    e = shap.explainers.Exact(m.predict, shap.maskers.Independent(bg, max_samples=len(bg)))
    theirs = e(ex).values
    np.testing.assert_allclose(ours, theirs, atol=1e-10)


@pytest.mark.parametrize("kind", ["boosting", "forest"])
def test_exact_shapley_values_match_tree_shap(kind):
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor

    X, y = _data(seed=1)
    m = (GradientBoostingRegressor(n_estimators=60, random_state=0) if kind == "boosting"
         else RandomForestRegressor(n_estimators=50, random_state=0)).fit(X, y)
    bg, ex = X[:60], X[200:240]
    ours = shapley_values(m.predict, ex, bg, [[j] for j in range(5)])
    t = shap.TreeExplainer(m, data=bg, feature_perturbation="interventional")
    np.testing.assert_allclose(ours, t.shap_values(ex), atol=1e-6)
    assert t.expected_value == pytest.approx(m.predict(bg).mean(), abs=1e-6)
