"""Tests for the B1 binary-vs-count Poisson target isolation."""

import numpy as np
import pytest

import poisson_target_isolation_b1 as isolate


class FakeClassifier:
    def predict_proba(self, X):
        scores = np.zeros(len(X))
        scores[0] = 1.0
        return np.column_stack([1.0 - scores, scores])


class FakePoisson:
    def __init__(self, positive_at):
        self.positive_at = positive_at

    def predict(self, X):
        scores = np.zeros(len(X))
        scores[self.positive_at] = 1.0
        return scores


def test_same_poisson_fit_receives_raw_counts_and_binary_presence():
    calls = []

    def cls_fit(X, y):
        calls.append(("classifier", y.copy()))
        return FakeClassifier()

    def poisson_fit(X, target):
        calls.append(("poisson", target.copy()))
        return FakePoisson(0 if np.max(target) > 1 else 1)

    y = np.array([True] + [False] * 19)
    counts = y.astype(float)
    counts[0] = 3.0
    rows, summary = isolate.run_experiment(
        np.zeros((20, 1)), y, counts, np.zeros((20, 1)), y, y.astype(float),
        expected_classifier=1.0, expected_count=1.0,
        fit_cls=cls_fit, fit_poisson=poisson_fit,
    )
    assert [row["setting"] for row in rows] == ["B_env_classifier", "binary_poisson", "count_poisson"]
    assert [name for name, _ in calls] == ["classifier", "poisson", "poisson"]
    np.testing.assert_array_equal(calls[1][1], counts)
    np.testing.assert_array_equal(calls[2][1], y.astype(float))
    assert summary["n_reports"] == 3
    assert rows[0]["capture@5%"] == 1.0
    assert rows[1]["capture@5%"] == 0.0
    assert rows[2]["capture@5%"] == 1.0
    assert all({"capture@1%", "capture@5%", "capture@10%", "auc", "ap"} <= row.keys()
               for row in rows)


def test_classifier_baseline_mismatch_stops_both_poisson_fits():
    calls = []

    def cls_fit(X, y):
        calls.append("classifier")
        return FakeClassifier()

    def poisson_fit(X, y):
        calls.append("poisson")
        return FakePoisson(0)

    y = np.array([True] + [False] * 19)
    with pytest.raises(ValueError, match="classifier baseline"):
        isolate.run_experiment(np.zeros((20, 1)), y, y.astype(float),
                               np.zeros((20, 1)), y, y.astype(float),
                               expected_classifier=0.0, expected_count=1.0,
                               fit_cls=cls_fit, fit_poisson=poisson_fit)
    assert calls == ["classifier"]


def test_count_reproduction_mismatch_stops_binary_fit():
    calls = []

    def cls_fit(X, y):
        calls.append("classifier")
        return FakeClassifier()

    def poisson_fit(X, y):
        calls.append("poisson")
        return FakePoisson(0)

    y = np.array([True] + [False] * 19)
    with pytest.raises(ValueError, match="count_poisson reproduction"):
        isolate.run_experiment(np.zeros((20, 1)), y, y.astype(float),
                               np.zeros((20, 1)), y, y.astype(float),
                               expected_classifier=1.0, expected_count=0.0,
                               fit_cls=cls_fit, fit_poisson=poisson_fit)
    assert calls == ["classifier", "poisson"]


def test_decision_uses_count_minus_binary_not_classifier():
    rows = [{"setting": "B_env_classifier", "capture@5%": 0.7},
            {"setting": "binary_poisson", "capture@5%": 0.4},
            {"setting": "count_poisson", "capture@5%": 0.5}]
    decision = isolate.decide(rows)
    assert decision["count_minus_binary_capture@5%"] == pytest.approx(0.1)
    assert decision["count_minus_classifier_capture@5%"] == pytest.approx(-0.2)
    assert decision["count_has_additional_signal_within_poisson"] is True
