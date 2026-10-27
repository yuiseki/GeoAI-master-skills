"""Tests for fixed B1 soft spatial labels and their two baselines."""

import numpy as np
import pytest

import model_eval as me
import soft_spatial_b1 as soft


def test_load_b1_only_returns_2023_and_2024_labels(tmp_path, monkeypatch):
    for name in ("worldcover", "dem", "worldpop", "osm"):
        np.savez(tmp_path / f"{name}.npz", value=np.array([1]))
    np.savez(tmp_path / "reports_by_year.npz", c2023=np.array([1]),
             c2024=np.array([2]), c2025=np.array([3]), c2026=np.array([4]))
    np.savez(tmp_path / "grid_mask.npz", muni=np.array([0]))
    monkeypatch.setattr(me.ft, "static_features", lambda *args: {"x": np.array([1])})
    _, counts, _ = soft.load_b1(tmp_path)
    assert list(counts) == [2023, 2024]


def test_soft_targets_use_nearest_positive_cell_center_distance():
    positive = np.zeros((7, 7), dtype=bool)
    positive[3, 3] = True
    inside = np.ones_like(positive)
    s100 = soft.make_targets(positive, inside, 100).reshape(7, 7)
    s200 = soft.make_targets(positive, inside, 200).reshape(7, 7)
    s300 = soft.make_targets(positive, inside, 300).reshape(7, 7)
    assert s100[3, 3] == s200[3, 3] == s300[3, 3] == 1.0
    assert s100[3, 4] == s200[3, 4] == s300[3, 4] == 0.5
    assert s100[4, 4] == 0.0  # diagonal center distance is sqrt(2) * 100 m
    assert s200[4, 4] == s300[4, 4] == 0.25
    assert s200[3, 5] == 0.25
    assert s200[4, 5] == 0.0
    assert s300[4, 5] == 0.125
    assert s300[3, 6] == 0.125
    assert s300[0, 0] == 0.0
    assert np.all((s100 <= s200) & (s200 <= s300))


def test_soft_targets_keep_outside_cells_out_and_positive_cells_at_one():
    positive = np.zeros((3, 3), dtype=bool)
    positive[1, 1] = True
    inside = np.ones_like(positive)
    inside[0, 1] = False
    labels = soft.make_targets(positive, inside, 100)
    assert len(labels) == 8
    assert np.count_nonzero(labels == 1.0) == 1
    assert np.count_nonzero(labels == 0.5) == 3


def test_fit_uses_same_hgb_params_and_no_sample_weight(monkeypatch):
    seen = []

    class Spy:
        def __init__(self, **kwargs):
            seen.append(("init", kwargs))

        def fit(self, X, y, **kwargs):
            seen.append(("fit", kwargs, y.copy()))
            return self

    monkeypatch.setattr("sklearn.ensemble.HistGradientBoostingClassifier", Spy)
    monkeypatch.setattr("sklearn.ensemble.HistGradientBoostingRegressor", Spy)
    X = np.zeros((3, 1))
    soft.fit_classifier(X, np.array([True, False, False]))
    soft.fit_regressor(X, np.array([1.0, 0.5, 0.0]))
    assert seen[0] == ("init", dict(me.HGB, random_state=0))
    assert seen[1][0:2] == ("fit", {})
    assert seen[2] == ("init", dict(me.HGB, random_state=0))
    assert seen[3][0:2] == ("fit", {})
    np.testing.assert_array_equal(seen[3][2], [1.0, 0.5, 0.0])


def test_classifier_baseline_gate_stops_before_regressor():
    calls = []

    class FakeClassifier:
        def predict_proba(self, X):
            scores = np.zeros(len(X))
            scores[0] = 1
            return np.column_stack([1 - scores, scores])

    def cls_fit(X, y):
        calls.append("classifier")
        return FakeClassifier()

    def reg_fit(X, y):
        calls.append("regressor")
        raise AssertionError("should not fit a regressor after a baseline mismatch")

    positive = np.zeros((4, 5), dtype=bool)
    positive[0, 0] = True
    inside = np.ones_like(positive)
    y = positive[inside]
    with pytest.raises(ValueError, match="baseline capture@5%"):
        soft.run_experiment(np.zeros((20, 1)), y, np.zeros((20, 1)), y,
                            y.astype(float), positive, inside, expected_baseline=0.0,
                            fit_cls=cls_fit, fit_reg=reg_fit)
    assert calls == ["classifier"]


def test_run_fits_only_three_fixed_soft_settings_after_two_controls():
    calls = []

    class FakeClassifier:
        def predict_proba(self, X):
            scores = np.linspace(1, 0, len(X))
            return np.column_stack([1 - scores, scores])

    class FakeRegressor:
        def predict(self, X):
            return np.linspace(1, 0, len(X))

    def cls_fit(X, y):
        calls.append(("classifier", sorted(np.unique(y).tolist())))
        return FakeClassifier()

    def reg_fit(X, y):
        calls.append(("regressor", sorted(np.unique(y).tolist())))
        return FakeRegressor()

    positive = np.zeros((4, 5), dtype=bool)
    positive[0, 0] = True
    inside = np.ones_like(positive)
    y = positive[inside]
    rows = soft.run_experiment(np.zeros((20, 1)), y, np.zeros((20, 1)), y,
                               y.astype(float), positive, inside, expected_baseline=1.0,
                               fit_cls=cls_fit, fit_reg=reg_fit)
    assert [row["setting"] for row in rows] == ["B_env_classifier", "hard_regressor", "S100", "S200", "S300"]
    assert [call[0] for call in calls] == ["classifier", "regressor", "regressor", "regressor", "regressor"]
    assert 0.5 in calls[2][1]
    assert 0.25 in calls[3][1]
    assert 0.125 in calls[4][1]
    assert all({"capture@1%", "capture@5%", "capture@10%", "auc", "ap"} <= row.keys()
               for row in rows)
