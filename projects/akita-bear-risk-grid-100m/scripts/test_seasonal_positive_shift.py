"""Small known-answer tests for the fixed seasonal positive-feature audit."""

import numpy as np
import pytest

import seasonal_positive_shift as shift


def test_later_minus_earlier_direction_missing_and_ks():
    result = shift.compare_feature(np.array([0., 1., 2., np.nan]),
                                   np.array([1., 2., 3., np.inf]))
    assert result["earlier"]["median"] == 1
    assert result["later"]["median"] == 2
    assert result["earlier"]["n_missing"] == 1
    assert result["later"]["n_missing"] == 1
    assert result["cliffs_delta_later_minus_earlier"] == pytest.approx(5 / 9)
    assert result["ks_statistic"] == pytest.approx(1 / 3)
    assert result["later"]["iqr"] == 1


def test_no_finite_values_stay_unknown_not_zero():
    result = shift.compare_feature(np.array([np.nan]), np.array([1.]))
    assert result["earlier"]["n_missing"] == 1
    assert result["cliffs_delta_later_minus_earlier"] is None
    assert result["ks_statistic"] is None


def test_top_five_absolute_delta_and_pairwise_contrast():
    pairs = {
        "2024_to_2025": {"features": {"a": {"cliffs_delta_later_minus_earlier": .7},
                                         "b": {"cliffs_delta_later_minus_earlier": -.4},
                                         "c": {"cliffs_delta_later_minus_earlier": .1}}},
        "2025_to_2026": {"features": {"a": {"cliffs_delta_later_minus_earlier": .2},
                                         "b": {"cliffs_delta_later_minus_earlier": -.8},
                                         "c": {"cliffs_delta_later_minus_earlier": .3}}},
    }
    summary = shift.rank_shifts(pairs)
    assert [row["feature"] for row in summary["top5_by_pair"]["2025_to_2026"]] == ["b", "c", "a"]
    assert summary["greater_in_2025_to_2026"][0]["feature"] == "b"
    assert summary["greater_in_2025_to_2026"][0]["increase_abs_delta"] == pytest.approx(.4)
    assert summary["greater_in_2025_to_2026"][0]["delta_2024_to_2025"] == -.4


def test_unaligned_features_or_labels_rejected():
    with pytest.raises(ValueError, match="aligned"):
        shift.audit_pair({"a": np.array([1., 2.])},
                         np.array([True]), np.array([True, False]))
