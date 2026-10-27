"""Tests for the isolated B1 hard-negative-mining exploration."""

import numpy as np
import pytest

import hard_negative_b1 as hn
import model_eval as me


def test_select_keeps_every_positive_and_disjoint_negatives():
    y = np.array([True, False, False, True, False, False, False, False, False, False])
    scores = np.array([0.1, 0.9, 0.8, 0.2, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2])
    selected, hard, random = hn.select_indices(y, scores, 2, seed=0)
    np.testing.assert_array_equal(hard, [1, 2])
    np.testing.assert_array_equal(selected[:2], [0, 3])
    assert len(random) == 2
    assert set(random).isdisjoint({0, 1, 2, 3})
    assert len(np.unique(selected)) == 6
    _, _, random_again = hn.select_indices(y, scores, 2, seed=0)
    np.testing.assert_array_equal(random, random_again)


def test_select_rejects_impossible_negative_budget():
    with pytest.raises(ValueError, match="twice"):
        hn.select_indices(np.array([True, False, False, False]), np.arange(4), 2)


def test_load_b1_never_reads_future_year_arrays(tmp_path, monkeypatch):
    for name in ("worldcover", "dem", "worldpop", "osm"):
        np.savez(tmp_path / f"{name}.npz", value=np.array([1]))
    np.savez(tmp_path / "reports_by_year.npz", c2023=np.array([1]),
             c2024=np.array([2]), c2025=np.array([3]), c2026=np.array([4]))
    np.savez(tmp_path / "grid_mask.npz", muni=np.array([0]))
    monkeypatch.setattr(me.ft, "static_features", lambda *args: {"x": np.array([1])})
    static, counts, muni = hn.load_b1(tmp_path)
    assert list(counts) == [2023, 2024]
    assert counts[2023].tolist() == [1.0]
    assert counts[2024].tolist() == [2.0]
    assert static["x"].tolist() == [1]
    assert muni.tolist() == [0]


def test_fit_keeps_existing_hgb_and_never_passes_sample_weight(monkeypatch):
    seen = {}

    class SpyHGB:
        def __init__(self, **kwargs):
            seen["params"] = kwargs

        def fit(self, X, y, **kwargs):
            seen["kwargs"] = kwargs
            seen["n"] = len(y)
            return self

    monkeypatch.setattr("sklearn.ensemble.HistGradientBoostingClassifier", SpyHGB)
    hn.fit_model(np.zeros((3, 1)), np.array([True, False, False]))
    assert seen == {"params": dict(me.HGB, random_state=0), "kwargs": {}, "n": 3}


def test_baseline_gate_stops_before_train_negative_scoring():
    calls = []

    class FakeModel:
        def predict_proba(self, X):
            calls.append(("predict", len(X)))
            score = np.zeros(len(X))
            score[0] = 0.9
            return np.column_stack([1 - score, score])

    def fake_fit(X, y):
        calls.append(("fit", len(X)))
        return FakeModel()

    y = np.array([True] + [False] * 19)
    with pytest.raises(ValueError, match="baseline capture@5%"):
        hn.run_experiment(np.zeros((20, 1)), y, np.zeros((20, 1)), y,
                          y.astype(float), expected_baseline=0.0, fit=fake_fit,
                          settings=(("HN1", 2),))
    assert calls == [("fit", 20), ("predict", 20)]


def test_only_fixed_variants_are_refit_from_scratch():
    calls = []

    class FakeModel:
        def predict_proba(self, X):
            score = np.linspace(1.0, 0.0, len(X))
            return np.column_stack([1 - score, score])

    def fake_fit(X, y):
        calls.append((len(y), int(y.sum())))
        return FakeModel()

    y = np.array([True] + [False] * 19)
    rows = hn.run_experiment(np.zeros((20, 1)), y, np.zeros((20, 1)), y,
                             y.astype(float), expected_baseline=1.0, fit=fake_fit,
                             settings=(("HN1", 2), ("HN3", 3), ("HN10", 4)))
    assert calls == [(20, 1), (5, 1), (7, 1), (9, 1)]
    assert [row["setting"] for row in rows] == ["baseline", "HN1", "HN3", "HN10"]
    assert all({"capture@1%", "capture@5%", "capture@10%", "auc", "ap"} <= row.keys()
               for row in rows)
    assert all(row["delta_capture@5%"] == 0.0 for row in rows)
