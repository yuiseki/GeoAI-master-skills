"""Known-answer checks for Q5 internal performance using unchanged global order."""

import numpy as np
import pytest

import crop_q5_internal_audit as audit
import metrics as mt


def test_q5_boundary_is_strict_and_non_q5_is_complement():
    q5 = audit.q5_mask(np.array([0.0, 0.025, 0.03, np.nan]), 0.025)
    assert q5.tolist() == [False, False, True, False]


def test_subsequence_preserves_global_tie_break_instead_of_reranking():
    scores = np.ones(40)
    mask = np.zeros(40, dtype=bool)
    mask[::3] = True
    global_order = mt.rank_order(scores, seed=0)
    subsequence = audit.order_within(global_order, mask)
    assert subsequence.tolist() == [i for i in global_order if mask[i]]
    assert set(subsequence) == set(np.flatnonzero(mask))


def test_internal_metrics_use_stratum_budget_and_global_top_allocation():
    scores = np.arange(20, 0, -1, dtype=float)
    positive = np.zeros(20, dtype=bool)
    positive[[0, 4, 10, 14]] = True
    crop = np.r_[np.ones(10), np.zeros(10)]
    result = audit.audit_year(scores, positive, crop, 0.025,
                              expected_capture=0.25,
                              expected_q5_cells=10,
                              expected_q5_positive=2,
                              expected_q5_global_captured=1)
    q5, other = result["strata"]["crop_Q5"], result["strata"]["non_Q5"]
    assert q5["n_cells"] == other["n_cells"] == 10
    assert q5["positive_rate"] == 0.2
    assert q5["auc"] == pytest.approx(13 / 16)
    assert q5["ap"] == pytest.approx(0.7)
    assert q5["capture_at_5_percent_within_stratum"] == pytest.approx(0.25)
    assert q5["capture_at_10_percent_within_stratum"] == pytest.approx(0.5)
    assert q5["capture_at_20_percent_within_stratum"] == pytest.approx(0.5)
    assert q5["n_global_top5_cells"] == 1
    assert q5["global_top5_allocation_rate"] == 0.1
    assert q5["n_global_top5_captured_positive"] == 1
    assert other["n_global_top5_cells"] == 0
    assert result["overall_capture_at_5"] == pytest.approx(0.25)


def test_saved_reference_mismatch_rejected():
    scores = np.arange(20, 0, -1, dtype=float)
    positive = np.zeros(20, dtype=bool)
    positive[0] = True
    crop = np.r_[np.ones(10), np.zeros(10)]
    with pytest.raises(ValueError, match="capture"):
        audit.audit_year(scores, positive, crop, 0.025,
                         expected_capture=0,
                         expected_q5_cells=10,
                         expected_q5_positive=1,
                         expected_q5_global_captured=1)
    with pytest.raises(ValueError, match="Q5"):
        audit.audit_year(scores, positive, crop, 0.025,
                         expected_capture=1,
                         expected_q5_cells=11,
                         expected_q5_positive=1,
                         expected_q5_global_captured=1)


def test_signal_rule_requires_both_years():
    years = {k: {"strata": {"crop_Q5": {"positive_rate": 0.1, "auc": 0.6,
                                        "ap": 0.2, "capture_at_5_percent_within_stratum": 0.12,
                                        "global_top5_allocation_rate": 0.02}}}
             for k in ("B2", "B3")}
    assert audit.interpret(years)["internal_rank_signal_both_years"] is True
    assert audit.interpret(years)["allocation_below_5_percent_both_years"] is True
    years["B3"]["strata"]["crop_Q5"]["auc"] = 0.5
    assert audit.interpret(years)["internal_rank_signal_both_years"] is False
