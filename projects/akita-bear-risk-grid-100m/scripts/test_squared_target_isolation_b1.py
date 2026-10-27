"""Tests for the fixed B1 squared-error binary-vs-count comparison."""

import numpy as np
import pytest

import model_eval as me
import squared_target_isolation_b1 as isolate


class FakeRegressor:
    def __init__(self, positive_at):
        self.positive_at = positive_at

    def predict(self, X):
        scores = np.zeros(len(X))
        scores[self.positive_at] = 1.0
        return scores


def test_same_squared_fit_receives_aligned_float32_binary_and_counts():
    calls = []

    def fake_fit(X, target):
        calls.append(target.copy())
        return FakeRegressor(0 if target.max() == 1 else 1)

    y = np.array([True] + [False] * 19)
    counts = y.astype(float)
    counts[0] = 3.0
    rows, summary = isolate.run_experiment(
        np.zeros((20, 1)), y, counts, np.zeros((20, 1)), y, y.astype(float),
        expected_binary=1.0, fit=fake_fit,
    )
    assert [row["setting"] for row in rows] == ["binary_squared", "count_squared"]
    assert len(calls) == 2
    assert calls[0].dtype == calls[1].dtype == np.float32
    np.testing.assert_array_equal(calls[0], y.astype(np.float32))
    np.testing.assert_array_equal(calls[1], counts.astype(np.float32))
    assert summary["n_reports"] == 3
    assert rows[0]["capture@5%"] == 1.0
    assert rows[1]["capture@5%"] == 0.0
    assert all({"capture@1%", "capture@5%", "capture@10%", "auc", "ap"} <= row.keys()
               for row in rows)


def test_binary_reproduction_failure_stops_before_count_fit():
    calls = []

    def fake_fit(X, target):
        calls.append(target.copy())
        return FakeRegressor(0)

    y = np.array([True] + [False] * 19)
    with pytest.raises(ValueError, match="binary_squared reproduction"):
        isolate.run_experiment(np.zeros((20, 1)), y, y.astype(float),
                               np.zeros((20, 1)), y, y.astype(float),
                               expected_binary=0.0, fit=fake_fit)
    assert len(calls) == 1


def test_fit_squared_keeps_hgb_settings_and_does_not_pass_weights(monkeypatch):
    seen = {}

    class SpyHGB:
        def __init__(self, **kwargs):
            seen["params"] = kwargs

        def fit(self, X, y, **kwargs):
            seen["kwargs"] = kwargs
            seen["target"] = y.copy()
            return self

    monkeypatch.setattr("sklearn.ensemble.HistGradientBoostingRegressor", SpyHGB)
    isolate.fit_squared(np.zeros((2, 1)), np.array([0., 2.], dtype=np.float32))
    assert seen["params"] == dict(me.HGB, random_state=0)
    assert seen["kwargs"] == {}
    np.testing.assert_array_equal(seen["target"], [0., 2.])


def test_reference_gate_rejects_mismatched_input_hashes():
    base = {"train_year": 2023, "test_year": 2024, "feature_names": ["x"],
            "input_sha256": {"a": "same"}, "hgb": me.HGB,
            "sklearn": "1.9.1", "sample_weight_passed": False}
    soft = {"setup": dict(base, soft_loss="squared_error"),
            "results": [{"setting": "hard_regressor", "capture@1%": 0.1,
                         "capture@5%": 0.5, "capture@10%": 0.7, "auc": 0.8, "ap": 0.02}]}
    poisson = {"setup": dict(base, loss="poisson"),
               "results": [{"setting": "binary_poisson", "capture@1%": 0.1,
                            "capture@5%": 0.4, "capture@10%": 0.7, "auc": 0.8, "ap": 0.02},
                           {"setting": "count_poisson", "capture@1%": 0.1,
                            "capture@5%": 0.6, "capture@10%": 0.7, "auc": 0.8, "ap": 0.02}]}
    with pytest.raises(ValueError, match="reference provenance"):
        isolate.validate_references(soft, poisson, {"a": "different"}, ["x"], "1.9.1")
    refs = isolate.validate_references(soft, poisson, {"a": "same"}, ["x"], "1.9.1")
    assert [row["setting"] for row in refs] == ["binary_poisson", "count_poisson"]


def test_decision_uses_squared_difference_even_if_poisson_differs():
    rows = [{"setting": "binary_squared", "capture@5%": 0.6},
            {"setting": "count_squared", "capture@5%": 0.5},
            {"setting": "binary_poisson", "capture@5%": 0.4},
            {"setting": "count_poisson", "capture@5%": 0.7}]
    decision = isolate.decide(rows)
    assert decision["count_minus_binary_squared_capture@5%"] == pytest.approx(-0.1)
    assert decision["count_minus_binary_poisson_capture@5%"] == pytest.approx(0.3)
    assert decision["count_signal_not_limited_to_poisson"] is False
