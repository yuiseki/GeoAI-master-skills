"""Tests for B1 count-target Poisson HGB exploration."""

import numpy as np
import pytest

import count_target_b1 as count_trial
import model_eval as me


def test_load_b1_only_uses_2023_and_2024_count_arrays(tmp_path, monkeypatch):
    for name in ("worldcover", "dem", "worldpop", "osm"):
        np.savez(tmp_path / f"{name}.npz", value=np.array([1]))
    np.savez(tmp_path / "reports_by_year.npz", c2023=np.array([2]),
             c2024=np.array([1]), c2025=np.array([3]), c2026=np.array([4]))
    np.savez(tmp_path / "grid_mask.npz", muni=np.array([0]))
    monkeypatch.setattr(me.ft, "static_features", lambda *args: {"x": np.array([1])})
    _, counts, _ = count_trial.load_b1(tmp_path)
    assert list(counts) == [2023, 2024]
    assert counts[2023].tolist() == [2.0]


def test_validate_targets_preserves_counts_above_one():
    y = np.array([False, True, True, False])
    counts = np.array([0., 1., 3., 0.])
    summary = count_trial.validate_targets(y, counts)
    assert summary == {"n_positive_cells": 2, "n_reports": 4, "n_cells_with_multiple_reports": 1,
                       "max_reports_in_cell": 3}
    np.testing.assert_array_equal(counts, [0., 1., 3., 0.])


@pytest.mark.parametrize("counts", [np.array([0., -1.]), np.array([0., 1.5]), np.array([0., np.nan])])
def test_validate_targets_rejects_invalid_counts(counts):
    with pytest.raises(ValueError, match="count target"):
        count_trial.validate_targets(np.array([False, True]), counts)


def test_fits_keep_existing_hgb_and_never_pass_sample_weight(monkeypatch):
    seen = []

    class SpyHGB:
        def __init__(self, **kwargs):
            seen.append(("init", kwargs))

        def fit(self, X, y, **kwargs):
            seen.append(("fit", kwargs, y.copy()))
            return self

    monkeypatch.setattr("sklearn.ensemble.HistGradientBoostingClassifier", SpyHGB)
    monkeypatch.setattr("sklearn.ensemble.HistGradientBoostingRegressor", SpyHGB)
    X = np.zeros((3, 1))
    count_trial.fit_classifier(X, np.array([True, False, True]))
    count_trial.fit_poisson(X, np.array([2., 0., 1.]))
    assert seen[0] == ("init", dict(me.HGB, random_state=0))
    assert seen[1][0:2] == ("fit", {})
    assert seen[2] == ("init", dict(me.HGB, loss="poisson", random_state=0))
    assert seen[3][0:2] == ("fit", {})
    np.testing.assert_array_equal(seen[3][2], [2., 0., 1.])


def test_baseline_mismatch_stops_before_poisson_fit():
    calls = []

    class FakeClassifier:
        def predict_proba(self, X):
            scores = np.zeros(len(X))
            scores[0] = 1.0
            return np.column_stack([1.0 - scores, scores])

    def cls_fit(X, y):
        calls.append("classifier")
        return FakeClassifier()

    def poisson_fit(X, counts):
        calls.append("poisson")
        raise AssertionError("Poisson should not fit after baseline mismatch")

    y = np.array([True] + [False] * 19)
    with pytest.raises(ValueError, match="baseline capture@5%"):
        count_trial.run_experiment(np.zeros((20, 1)), y, y.astype(float),
                                   np.zeros((20, 1)), y, y.astype(float),
                                   expected_baseline=0.0, fit_cls=cls_fit,
                                   fit_count=poisson_fit)
    assert calls == ["classifier"]


def test_evaluates_poisson_scores_against_binary_2024_labels():
    calls = []

    class FakeClassifier:
        def predict_proba(self, X):
            scores = np.zeros(len(X))
            scores[0] = 1.0
            return np.column_stack([1.0 - scores, scores])

    class FakePoisson:
        def predict(self, X):
            scores = np.zeros(len(X))
            scores[1] = 3.0
            return scores

    def cls_fit(X, y):
        calls.append(("classifier", y.tolist()))
        return FakeClassifier()

    def poisson_fit(X, counts):
        calls.append(("poisson", counts.tolist()))
        return FakePoisson()

    y = np.array([True] + [False] * 19)
    train_counts = y.astype(float)
    train_counts[0] = 3.0
    rows, summary = count_trial.run_experiment(np.zeros((20, 1)), y, train_counts,
                                               np.zeros((20, 1)), y, y.astype(float),
                                               expected_baseline=1.0, fit_cls=cls_fit,
                                               fit_count=poisson_fit)
    assert [row["setting"] for row in rows] == ["B_env_classifier", "count_poisson"]
    assert summary["n_reports"] == 3
    assert calls[1] == ("poisson", train_counts.tolist())
    assert rows[0]["capture@5%"] == 1.0
    assert rows[1]["capture@5%"] == 0.0
    assert rows[1]["delta_capture@5%"] == -1.0
    assert all({"capture@1%", "capture@5%", "capture@10%", "auc", "ap"} <= row.keys()
               for row in rows)
