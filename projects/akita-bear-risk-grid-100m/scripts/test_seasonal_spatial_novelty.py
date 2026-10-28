"""Known-answer distance and overlap checks for the fixed seasonal novelty audit."""

import numpy as np
import pytest

import seasonal_spatial_novelty as audit


def test_exact_cell_and_inclusive_distance_thresholds():
    past = np.zeros((1, 11), dtype=bool)
    past[0, 0] = True
    target = np.zeros_like(past)
    target[0, [0, 1, 3, 5, 10]] = True
    result = audit.summarize(target, past, cell_size_m=100)
    assert result["n_target_positive"] == 5
    assert result["n_past_union_positive"] == 1
    assert result["same_cell"] == {"count": 1, "share": .2}
    assert result["nearest_distance_m"]["median"] == 300
    assert result["nearest_distance_m"]["p90"] == 800
    assert [result["within_distance_m"][str(d)]["count"] for d in (100, 300, 500, 1000)] == [2, 3, 4, 5]


def test_union_is_unique_cells_not_sum_of_yearly_counts():
    earlier = np.array([[True, False, True]])
    later = np.array([[True, True, False]])
    union = audit.past_union({2023: earlier, 2024: later}, (2023, 2024))
    assert union.tolist() == [[True, True, True]]
    with pytest.raises(ValueError, match="same shape"):
        audit.past_union({2023: earlier, 2024: np.array([True])}, (2023, 2024))


def test_empty_past_or_target_is_not_silently_zero():
    empty = np.zeros((2, 2), dtype=bool)
    nonempty = empty.copy()
    nonempty[0, 0] = True
    with pytest.raises(ValueError, match="non-empty"):
        audit.summarize(nonempty, empty, cell_size_m=100)
    with pytest.raises(ValueError, match="non-empty"):
        audit.summarize(empty, nonempty, cell_size_m=100)
