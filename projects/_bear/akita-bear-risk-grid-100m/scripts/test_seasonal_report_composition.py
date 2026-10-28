"""Known-answer checks for the fixed seasonal composition audit."""

import numpy as np
import pytest

from grid import Grid
import seasonal_report_composition as audit


def test_js_divergence_is_bits_and_zero_cells_are_supported():
    assert audit.js_divergence([1, 0], [0, 1]) == pytest.approx(1.0)
    assert audit.js_divergence([2, 2], [5, 5]) == pytest.approx(0.0)
    with pytest.raises(ValueError, match="positive totals"):
        audit.js_divergence([0, 0], [1, 0])


def test_grid_assignment_and_municipal_positive_count_reconcile():
    grid = Grid(0, 0, 3, 2, 100)
    muni = np.array([[0, 0, 1], [1, 1, 1]])
    x = np.array([50, 50, 250, 150, 400])
    y = np.array([50, 50, 50, 150, 50])
    assigned = audit.assign_municipality(grid, muni, x, y)
    assert assigned.tolist() == [0, 0, 1, 1, -1]
    cell_counts = np.array([[2, 0, 1], [0, 1, 0]])
    result = audit.summarize_year(muni, cell_counts, assigned[:4],
                                  ["目撃", "目撃", "痕跡", None],
                                  ["001", "002"], ["A", "B"])
    assert result["n_reports"] == 4
    assert result["n_positive_cells"] == 3
    assert [row["report_count"] for row in result["municipalities"]] == [2, 2]
    assert [row["positive_cell_count"] for row in result["municipalities"]] == [1, 2]
    assert result["info_types"]["目撃"]["count"] == 2
    assert result["info_types"]["(欠損)"]["count"] == 1


def test_share_change_orders_by_absolute_percentage_points():
    changes = audit.compare_counts({"A": 8, "B": 2}, {"A": 3, "B": 7}, top_n=2)
    assert changes["js_divergence_bits"] > 0
    assert {row["category"] for row in changes["largest_share_changes"]} == {"A", "B"}
    assert changes["largest_share_changes"][0]["absolute_change_percentage_points"] == pytest.approx(50)
