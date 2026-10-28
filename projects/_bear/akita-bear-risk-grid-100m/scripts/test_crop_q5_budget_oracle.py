"""Known-answer tests for fixed-budget, two-stratum diagnostic oracle."""

import numpy as np
import pytest

import crop_q5_budget_oracle as oracle


def test_all_integer_allocations_use_exact_same_budget_and_fixed_orders():
    # Scores already descend in array order. Current global top-2 is 0,1.
    score = np.arange(40, 0, -1, dtype=float)
    q5 = np.arange(40) % 2 == 0
    positive = np.zeros(40, dtype=bool)
    positive[[2, 4]] = True
    result = oracle.audit_year(score, positive, q5,
                               expected_fractional_capture=0,
                               expected_q5_cells=20,
                               expected_q5_positive=2,
                               expected_ceil_q5_selected=1,
                               expected_ceil_q5_captured=0)
    assert result["budget_cells"] == 2
    assert result["feasible_q5_allocation_min"] == 0
    assert result["feasible_q5_allocation_max"] == 2
    assert result["current"]["q5_selected_cells"] == 1
    assert result["current"]["captured_positive"] == 0
    assert result["curve"]["captured_positive_by_q5_cells"] == [0, 0, 1]
    assert result["curve"]["capture_by_q5_cells"] == [0, 0, 0.5]
    assert result["oracle"]["q5_selected_cells"] == 2
    assert result["oracle"]["capture"] == 0.5
    assert result["oracle_minus_current"]["captured_positive"] == 1


def test_tied_optimum_reports_full_range_and_nearest_current():
    score = np.arange(40, 0, -1, dtype=float)
    q5 = np.arange(40) % 2 == 0
    positive = np.zeros(40, dtype=bool)
    positive[0] = True
    result = oracle.audit_year(score, positive, q5,
                               expected_fractional_capture=1,
                               expected_q5_cells=20,
                               expected_q5_positive=1,
                               expected_ceil_q5_selected=1,
                               expected_ceil_q5_captured=1)
    assert result["curve"]["captured_positive_by_q5_cells"] == [0, 1, 1]
    assert result["oracle"]["all_optimal_q5_cells_min"] == 1
    assert result["oracle"]["all_optimal_q5_cells_max"] == 2
    assert result["oracle"]["q5_selected_cells"] == 1


def test_partial_endpoint_is_not_compared_with_integer_budget():
    # n=21: original fractional capture gives 5% of 21 = 1.05 cells,
    # while the fixed integer budget has floor(1.05)=1 cell.
    score = np.arange(21, 0, -1, dtype=float)
    q5 = np.arange(21) % 2 == 0
    positive = np.zeros(21, dtype=bool)
    positive[[0, 1]] = True
    result = oracle.audit_year(score, positive, q5,
                               expected_fractional_capture=0.525,
                               expected_q5_cells=11,
                               expected_q5_positive=1,
                               expected_ceil_q5_selected=1,
                               expected_ceil_q5_captured=1)
    assert result["budget_cells"] == 1
    assert result["current"]["capture"] == 0.5
    assert result["original_fractional_capture_at_5"] == pytest.approx(0.525)


def test_rejects_wrong_provenance_or_invalid_partition():
    score = np.arange(40, 0, -1, dtype=float)
    positive = np.zeros(40, dtype=bool)
    positive[0] = True
    q5 = np.arange(40) % 2 == 0
    with pytest.raises(ValueError, match="fractional capture"):
        oracle.audit_year(score, positive, q5,
                          expected_fractional_capture=0,
                          expected_q5_cells=20,
                          expected_q5_positive=1,
                          expected_ceil_q5_selected=1,
                          expected_ceil_q5_captured=1)
    with pytest.raises(ValueError, match="Q5"):
        oracle.audit_year(score, positive, q5,
                          expected_fractional_capture=1,
                          expected_q5_cells=19,
                          expected_q5_positive=1,
                          expected_ceil_q5_selected=1,
                          expected_ceil_q5_captured=1)
