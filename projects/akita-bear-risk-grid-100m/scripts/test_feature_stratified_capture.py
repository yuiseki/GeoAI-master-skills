"""Known-answer checks for fixed, whole-prefecture feature strata."""

import numpy as np
import pytest

import feature_stratified_capture as audit


def test_whole_grid_cutpoints_and_ties_are_not_split():
    values = np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 2, np.nan], dtype=float)
    cuts, strata = audit.quintile_strata(values)
    assert cuts.tolist() == [0.0, 0.0, 0.0, pytest.approx(0.2)]
    assert np.all(strata[:8] == 0)
    assert strata[8] == 4
    assert strata[10] == -1


def test_counts_recall_positive_share_empty_and_missing():
    # 20 cells: top 5% is exactly the first one; quintiles use all finite cells.
    values = np.array([0] * 16 + [1] * 3 + [np.nan], dtype=float)
    score = np.arange(20, 0, -1, dtype=float)
    positive = np.zeros(20, dtype=bool)
    positive[[0, 2, 16, 19]] = True
    result = audit.audit_year(score, positive, {"crop": values},
                              expected_capture=0.25, expected_captured=1,
                              expected_missed=3)
    rows = result["features"]["crop"]["strata"]
    assert [r["n_cells"] for r in rows] == [16, 0, 0, 0, 3, 1]
    assert [r["n_positive"] for r in rows] == [2, 0, 0, 0, 1, 1]
    assert [r["n_captured_positive"] for r in rows] == [1, 0, 0, 0, 0, 0]
    assert rows[0]["recall"] == 0.5
    assert rows[0]["share_of_all_positives"] == 0.5
    assert rows[1]["recall"] is None
    assert rows[-1]["stratum"] == "missing"
    assert rows[-1]["share_of_all_positives"] == 0.25
    assert result["n_positive"] == 4


def test_rejects_misalignment_or_wrong_saved_capture():
    score = np.arange(20, 0, -1, dtype=float)
    positive = np.zeros(20, dtype=bool)
    positive[0] = True
    with pytest.raises(ValueError, match="capture"):
        audit.audit_year(score, positive, {"crop": np.zeros(20)},
                         expected_capture=0, expected_captured=1, expected_missed=0)
    with pytest.raises(ValueError, match="aligned"):
        audit.audit_year(score, positive, {"crop": np.zeros(19)},
                         expected_capture=1, expected_captured=1, expected_missed=0)


def test_consistent_low_requires_both_years_and_positive_cells():
    years = {"B2": {"overall_recall": 0.55, "features": {
        "crop": {"strata": [{"stratum": "Q5", "n_positive": 10, "recall": 0.4}]} }},
             "B3": {"overall_recall": 0.54, "features": {
        "crop": {"strata": [{"stratum": "Q5", "n_positive": 6, "recall": 0.3}]}}}}
    assert audit.consistent_low(years, "crop", "Q5") is True
    years["B3"]["features"]["crop"]["strata"][0]["recall"] = 0.6
    assert audit.consistent_low(years, "crop", "Q5") is False
    years["B3"]["features"]["crop"]["strata"][0]["n_positive"] = 0
    assert audit.consistent_low(years, "crop", "Q5") is False
