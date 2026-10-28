"""uvx --with pytest --with numpy --with scipy --with scikit-learn pytest -q scripts/test_weight_sweep_b1.py"""

import numpy as np
import pytest

import model_eval as me
import weight_sweep_b1 as sweep


def test_sample_weights_only_change_positive_cells():
    y = np.array([False, True, False, True])
    weights, totals = sweep.sample_weights(y, 3)
    np.testing.assert_array_equal(weights, [1, 3, 1, 3])
    assert totals == {"positive": 6.0, "negative": 2.0}


def test_fit_passes_explicit_weights_without_changing_hgb(monkeypatch):
    seen = {}

    class SpyHGB:
        def __init__(self, **kwargs):
            seen["kwargs"] = kwargs

        def fit(self, X, y, *, sample_weight=None):
            seen["X"] = X
            seen["y"] = y
            seen["sample_weight"] = sample_weight
            return self

        def predict_proba(self, X):
            return np.column_stack([np.full(len(X), 0.75), np.full(len(X), 0.25)])

    monkeypatch.setattr("sklearn.ensemble.HistGradientBoostingClassifier", SpyHGB)
    X = np.array([[0.0], [1.0], [2.0]])
    y = np.array([False, True, False])
    scores, totals = sweep.fit_predict(X, y, X[:2], 10)
    assert seen["kwargs"] == dict(me.HGB, random_state=0)
    np.testing.assert_array_equal(seen["sample_weight"], [1, 10, 1])
    np.testing.assert_array_equal(scores, [0.25, 0.25])
    assert totals == {"positive": 10.0, "negative": 2.0}


def test_existing_baseline_does_not_pass_sample_weight(monkeypatch):
    seen = []

    class SpyHGB:
        def __init__(self, **kwargs):
            pass

        def fit(self, X, y, **kwargs):
            seen.append(kwargs)
            return self

        def predict_proba(self, X):
            return np.column_stack([np.full(len(X), 0.75), np.full(len(X), 0.25)])

    monkeypatch.setattr("sklearn.ensemble.HistGradientBoostingClassifier", SpyHGB)
    y = np.array([False, True, False])
    _, totals = sweep.fit_predict(np.zeros((3, 1)), y, np.zeros((2, 1)), None)
    assert seen == [{}]
    assert totals == {"positive": 1.0, "negative": 2.0}


def test_baseline_mismatch_stops_before_candidates():
    calls = []

    def fake_fit(Xtr, ytr, Xte, weight):
        calls.append(weight)
        return np.array([0.1, 0.9] + [0.0] * 18), {"positive": float(weight or 1), "negative": 19.0}

    y = np.array([True] + [False] * 19)
    with pytest.raises(ValueError, match="baseline capture@5%"):
        sweep.run_sweep(np.zeros((20, 1)), y, np.zeros((20, 1)), y,
                        expected_baseline=1.0, fit=fake_fit)
    assert calls == [None]


def test_sweep_uses_only_four_fixed_weights_and_existing_metrics():
    calls = []

    def fake_fit(Xtr, ytr, Xte, weight):
        calls.append(weight)
        score = np.zeros(20)
        score[0 if weight in (None, 1, 10) else 1] = 1.0
        return score, {"positive": float(weight or 1), "negative": 19.0}

    y = np.array([True] + [False] * 19)
    rows = sweep.run_sweep(np.zeros((20, 1)), y, np.zeros((20, 1)), y,
                           expected_baseline=1.0, fit=fake_fit)
    assert calls == [None, 1, 3, 10, 30]
    assert [r["positive_weight"] for r in rows] == [1, 1, 3, 10, 30]
    assert [r["sample_weight_passed"] for r in rows] == [False, True, True, True, True]
    assert rows[0]["capture@5%"] == 1.0
    assert rows[2]["capture@5%"] == 0.0
    assert all({"capture@1%", "capture@5%", "capture@10%", "auc", "ap"} <= r.keys() for r in rows)
