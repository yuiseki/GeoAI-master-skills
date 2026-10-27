"""Small contract tests for the fixed B2/B3 Poisson robustness comparison."""

import numpy as np
import pytest

import poisson_robustness_b2_b3 as robust


class FakeClassifier:
    def predict_proba(self, X):
        p = np.linspace(0.0, 1.0, len(X))
        return np.column_stack([1.0 - p, p])


class FakePoisson:
    def predict(self, X):
        return np.linspace(0.0, 1.0, len(X))


def test_fixed_split_years_and_targets_no_future_leakage():
    X = np.zeros((20, 2), dtype=np.float32)
    counts = {2023: np.array([2] + [0] * 19, dtype=float),
              2024: np.array([0, 3] + [0] * 18, dtype=float),
              2025: np.array([0, 0, 4] + [0] * 17, dtype=float),
              2026: np.array([0, 0, 0, 5] + [0] * 16, dtype=float)}
    calls = []

    def fit_cls(x, y):
        calls.append(("classifier", len(x), y.copy()))
        return FakeClassifier()

    def fit_poisson(x, y):
        calls.append(("poisson", len(x), y.copy()))
        return FakePoisson()

    for block, train, test in robust.SPLITS:
        rows, meta = robust.run_split(X, counts, train, test, fit_cls=fit_cls,
                                      fit_poisson=fit_poisson, expected_classifier=None)
        assert [r["setting"] for r in rows] == ["B_env_classifier", "binary_poisson", "count_poisson"]
        expected_counts = np.concatenate([counts[y] for y in train])
        assert [name for name, _, _ in calls[-3:]] == ["classifier", "poisson", "poisson"]
        np.testing.assert_array_equal(calls[-3][2], expected_counts > 0)
        np.testing.assert_array_equal(calls[-2][2], (expected_counts > 0).astype(float))
        np.testing.assert_array_equal(calls[-1][2], expected_counts)
        assert all(n == 20 * len(train) for _, n, _ in calls[-3:])
        assert meta["test_year"] == test and meta["n_test_positive"] == 1
        assert all(set(robust.METRICS) <= r.keys() for r in rows)


def test_classifier_mismatch_stops_poisson_models():
    counts = {2023: np.array([1] + [0] * 19, dtype=float),
              2024: np.array([0, 1] + [0] * 18, dtype=float),
              2025: np.array([1] + [0] * 19, dtype=float)}
    calls = []

    def fit_cls(x, y):
        calls.append("classifier")
        return FakeClassifier()

    def fit_poisson(x, y):
        calls.append("poisson")
        return FakePoisson()

    with pytest.raises(ValueError, match="classifier baseline"):
        robust.run_split(np.zeros((20, 1)), counts, (2023, 2024), 2025,
                         fit_cls=fit_cls, fit_poisson=fit_poisson,
                         expected_classifier=2.0)
    assert calls == ["classifier"]


def test_decision_requires_both_followup_differences_positive():
    assert robust.decide({"B2": 0.01, "B3": 0.02})["verdict"] == "robust_same_direction"
    assert robust.decide({"B2": 0.01, "B3": -0.01})["verdict"] == "mixed_not_robust"
    assert robust.decide({"B2": -0.01, "B3": 0.0})["verdict"] == "reversed_or_flat"
