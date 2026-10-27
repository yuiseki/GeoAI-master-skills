"""Fixed-score fold-local audit and reproduction gates."""

import numpy as np
import pytest

import fold_local_oof_audit as audit
import same_year_spatial_oof as spatial


def test_fold_local_removes_cross_fold_score_offset_without_changing_within_fold_order():
    scores = np.r_[np.linspace(0.51, 1.0, 100), np.linspace(0.0, 0.49, 100)]
    folds = np.r_[np.zeros(100, dtype=np.int8), np.ones(100, dtype=np.int8)]
    positive = np.zeros(200, dtype=bool)
    positive[[99, 199]] = True
    result = audit.fold_local_capture(scores, positive, folds, fractions=(0.05,))
    assert result["global"]["capture@5%"] == 0.5
    assert result["fold_local"]["capture@5%"] == 1.0
    assert result["delta_fold_local_minus_global"]["capture@5%"] == 0.5
    assert [row["selected_cells"]["5%"] for row in result["folds"]] == [5, 5]
    assert [row["captured_positive_integer"]["5%"] for row in result["folds"]] == [1, 1]


def test_fractional_boundary_and_zero_positive_fold_are_accounted_for():
    scores = np.r_[np.arange(10, dtype=float), np.arange(10, dtype=float) - 10]
    folds = np.r_[np.zeros(10, dtype=np.int8), np.ones(10, dtype=np.int8)]
    positive = np.zeros(20, dtype=bool)
    positive[9] = True
    result = audit.fold_local_capture(scores, positive, folds, fractions=(0.05,))
    assert result["fold_local"]["capture@5%"] == 0.5
    assert result["folds"][0]["captured_positive_equivalent"]["5%"] == 0.5
    assert result["folds"][0]["selected_cells"]["5%"] == 1
    assert result["folds"][1]["recall"]["5%"] is None


def test_reproduction_gate_checks_all_five_metrics():
    current = {key: 0.3 for key in spatial.METRICS}
    spatial.assert_reproduced(current, current, "B2")
    for key in spatial.METRICS:
        changed = dict(current)
        changed[key] += 1e-6
        with pytest.raises(ValueError, match=key):
            spatial.assert_reproduced(changed, current, "B2")


def test_audit_rejects_nonbinary_or_misaligned_arrays():
    scores = np.arange(20, dtype=float)
    labels = np.arange(20) % 2 == 0
    folds = np.arange(20) % 2
    with pytest.raises(ValueError):
        audit.fold_local_capture(scores, labels.astype(int), folds)
    with pytest.raises(ValueError):
        audit.fold_local_capture(scores[:-1], labels, folds)
