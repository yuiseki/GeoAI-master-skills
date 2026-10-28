"""Known-answer tests for fixed-score municipal capture decomposition."""

import numpy as np
import pytest

import fixed_score_municipal_decomposition as audit


def test_same_top_cells_used_for_both_years():
    score = np.arange(20, 0, -1, dtype=float)
    top = audit.fixed_top_mask(score)
    assert np.flatnonzero(top).tolist() == [0]
    muni = np.array([0] * 10 + [1] * 10)
    y25 = np.zeros(20, dtype=bool)
    y26 = np.zeros(20, dtype=bool)
    y25[[0, 10]] = True
    y26[[0, 1, 10]] = True
    a = audit.audit_year(y25, top, muni, ["001", "002"], ["A", "B"])
    b = audit.audit_year(y26, top, muni, ["001", "002"], ["A", "B"])
    assert a["capture"] == .5
    assert b["capture"] == pytest.approx(1 / 3)
    assert b["municipalities"][0]["n_captured"] == 1
    assert b["municipalities"][0]["recall"] == .5


def test_kitagawa_composition_and_within_reconcile():
    old = {"municipalities": [
        {"code5": "A", "name": "A", "n_positive": 2, "n_captured": 2, "positive_share": .5, "recall": 1.},
        {"code5": "B", "name": "B", "n_positive": 2, "n_captured": 0, "positive_share": .5, "recall": 0.}],
        "n_positive": 4, "capture": .5}
    new = {"municipalities": [
        {"code5": "A", "name": "A", "n_positive": 1, "n_captured": 1, "positive_share": .25, "recall": 1.},
        {"code5": "B", "name": "B", "n_positive": 3, "n_captured": 0, "positive_share": .75, "recall": 0.}],
        "n_positive": 4, "capture": .25}
    result = audit.decompose(old, new)
    assert result["composition_component"] == pytest.approx(-.25)
    assert result["within_component"] == pytest.approx(0)
    assert result["unallocated_zero_positive_component"] == 0
    assert result["composition_share_of_decline"] == pytest.approx(1)


def test_zero_positive_municipality_is_unallocated_not_imputed():
    old = {"municipalities": [
        {"code5": "A", "name": "A", "n_positive": 2, "n_captured": 1, "positive_share": 1., "recall": .5},
        {"code5": "B", "name": "B", "n_positive": 0, "n_captured": 0, "positive_share": 0., "recall": None}],
        "n_positive": 2, "capture": .5}
    new = {"municipalities": [
        {"code5": "A", "name": "A", "n_positive": 2, "n_captured": 1, "positive_share": .5, "recall": .5},
        {"code5": "B", "name": "B", "n_positive": 2, "n_captured": 1, "positive_share": .5, "recall": .5}],
        "n_positive": 4, "capture": .5}
    result = audit.decompose(old, new)
    assert result["composition_component"] == pytest.approx(-.25)
    assert result["within_component"] == 0
    assert result["unallocated_zero_positive_component"] == pytest.approx(.25)
    assert result["zero_positive_municipalities"][0]["code5"] == "B"
