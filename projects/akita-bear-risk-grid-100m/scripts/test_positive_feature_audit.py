"""Known-answer tests for captured-vs-missed B_env feature descriptions."""

import numpy as np
import pytest

import positive_feature_audit as audit


def test_feature_summary_keeps_missing_out_of_quantiles_and_records_it():
    result = audit.summarize_feature(np.array([1.0, 2.0, 3.0, np.nan]),
                                     np.array([0.0, 1.0, 2.0, 4.0]))
    assert result["captured"]["n_total"] == 4
    assert result["captured"]["n_missing"] == 1
    assert result["captured"]["median"] == 2.0
    assert result["missed"]["median"] == 1.5
    assert result["captured_minus_missed_median"] == 0.5
    assert result["ks_statistic"] == pytest.approx(0.25)
    assert result["cliffs_delta"] == pytest.approx(1 / 6)


def test_zero_inflation_has_direction_even_when_medians_tie():
    result = audit.summarize_feature(np.array([0.0, 0.0, 1.0]),
                                     np.array([0.0, 0.0, 0.0]))
    assert result["captured_minus_missed_median"] == 0
    assert result["cliffs_delta"] > 0


def test_top5_split_reproduces_saved_capture_and_counts():
    score = np.arange(20, 0, -1, dtype=float)
    positive = np.zeros(20, dtype=bool)
    positive[[0, 1, 5]] = True
    features = {"a": np.arange(20, dtype=float), "b": np.ones(20)}
    result = audit.audit_year(score, positive, features, expected_capture=1 / 3,
                              expected_captured=1, expected_missed=2)
    assert result["n_captured_positive"] == 1
    assert result["n_missed_positive"] == 2
    assert result["features"]["a"]["captured"]["median"] == 0
    assert result["features"]["a"]["missed"]["median"] == 3
    assert result["features"]["b"]["cliffs_delta"] == 0
    with pytest.raises(ValueError, match="capture"):
        audit.audit_year(score, positive, features, expected_capture=0,
                         expected_captured=1, expected_missed=2)


def test_same_direction_rank_uses_weaker_year_effect_and_ignores_reversal():
    years = {
        "B2": {"features": {"a": {"cliffs_delta": 0.8}, "b": {"cliffs_delta": -0.4},
                            "c": {"cliffs_delta": 0.2}, "d": {"cliffs_delta": 0.0}}},
        "B3": {"features": {"a": {"cliffs_delta": 0.3}, "b": {"cliffs_delta": 0.5},
                            "c": {"cliffs_delta": 0.1}, "d": {"cliffs_delta": 0.8}}},
    }
    ranked = audit.rank_consistent(years)
    assert [row["feature"] for row in ranked] == ["a", "c"]
    assert ranked[0]["direction"] == "captured_higher"
    assert ranked[0]["min_abs_cliffs_delta"] == 0.3


def test_landcover_cell_fraction_and_neighbourhood_mean_are_distinguished():
    assert audit.feature_unit("crop") == "fraction of valid WorldCover pixels in 100m cell"
    assert audit.feature_unit("crop_500") == "mean 100m-cell fraction in square window"
    assert audit.feature_unit("forest_edge") == "m"
