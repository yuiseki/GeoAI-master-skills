"""Known-answer and failure-case tests for the saved-score false-negative audit."""

import numpy as np
import pytest

import false_negative_audit as audit
import metrics as mt


def test_rank_buckets_and_nearest_top_cell_distance():
    score = np.arange(20, 0, -1, dtype=float)
    positive = np.zeros(20, dtype=bool)
    positive[[0, 1, 3, 11, 19]] = True
    result = audit.summarize(score, positive, np.arange(20), np.zeros(20, dtype=int),
                             size_m=100, reference_capture=0.2)
    assert result["n_top5_cells"] == 1
    assert result["n_positive"] == 5
    assert result["n_missed_positive"] == 4
    assert result["rank_bins_counts"] == {"5-10%": 1, "10-25%": 1, "25-50%": 0, "50-100%": 2}
    assert result["within_distance_m"]["100"] == {"count": 1, "share": 0.25}
    assert result["within_distance_m"]["300"] == {"count": 2, "share": 0.5}
    assert result["rank_bins_within_distance_counts"]["300"] == {
        "5-10%": 1, "10-25%": 1, "25-50%": 0, "50-100%": 0,
    }
    assert result["within_distance_m"]["500"] == {"count": 2, "share": 0.5}
    assert result["within_distance_m"]["1000"] == {"count": 2, "share": 0.5}
    assert result["distance_m"]["median"] == 700.0
    assert result["distance_m"]["p90"] == pytest.approx(1660.0)


def test_euclidean_grid_centres_and_fractional_capture_boundary():
    score = np.arange(21, 0, -1, dtype=float)
    positive = np.zeros(21, dtype=bool)
    positive[[0, 1, 2, 3]] = True
    # 21 cells: 5% is 1.05, so the binary top set contains cells 0 and 1.
    reference = mt.capture(mt.rank_order(score, seed=0), positive, 0.05)
    ix = np.array([0, 2, 1] + list(range(3, 21)))
    iy = np.array([0, 0, 1] + [0] * 18)
    result = audit.summarize(score, positive, ix, iy, size_m=100,
                             reference_capture=reference)
    assert result["n_top5_cells"] == 2
    assert result["n_missed_positive"] == 2
    assert result["distance_m"]["median"] == pytest.approx((100 * 2**0.5 + 100) / 2)
    assert result["capture_at_5_from_saved_scores"] == pytest.approx(reference)


def test_saved_score_capture_mismatch_fails_closed():
    score = np.arange(20, 0, -1, dtype=float)
    positive = np.zeros(20, dtype=bool)
    positive[0] = True
    with pytest.raises(ValueError, match="capture@5%"):
        audit.summarize(score, positive, np.arange(20), np.zeros(20, dtype=int),
                        size_m=100, reference_capture=0.0)


def test_bad_layout_fails_closed():
    with pytest.raises(ValueError, match="aligned"):
        audit.summarize(np.ones(3), np.ones(3, dtype=bool), np.arange(2), np.zeros(3),
                        size_m=100, reference_capture=None)


def test_priority_uses_pooled_missed_positive_not_average_of_year_shares():
    summaries = {
        "B2": {"n_missed_positive": 9, "rank_bins_counts": {"5-10%": 4},
               "within_distance_m": {"300": {"count": 3}}},
        "B3": {"n_missed_positive": 1, "rank_bins_counts": {"5-10%": 1},
               "within_distance_m": {"300": {"count": 1}}},
    }
    assert audit.decide_priority(summaries)["priority"] == "new_explanatory_variables"
    summaries["B2"]["rank_bins_counts"]["5-10%"] = 6
    assert audit.decide_priority(summaries)["priority"] == "ranking_improvement"
    summaries["B2"]["rank_bins_counts"]["5-10%"] = 4
    summaries["B2"]["within_distance_m"]["300"]["count"] = 6
    assert audit.decide_priority(summaries)["priority"] == "position_accuracy_audit"
