"""uv run --no-project --with pytest --with numpy python3 -m pytest -q projects/japan-grid-population-audit/scripts/test_diagnostics.py"""

import pytest
from diagnostics import coarsen, mesh_indices, pearson


def test_mesh_indices_follow_third_mesh_digits():
    assert mesh_indices("53394610") == (53 * 80 + 4 * 10 + 1, 39 * 80 + 6 * 10 + 0)
    assert mesh_indices("53394611") == (53 * 80 + 4 * 10 + 1, 39 * 80 + 6 * 10 + 1)


def test_coarsen_requires_complete_block_and_aggregates_amounts():
    rows = [
        {
            "mesh_code": f"m{r}{c}",
            "grid_row": r,
            "grid_col": c,
            "census_population": 10,
            "ghsl_area": 5,
            "built_share": float(r + c) / 2,
            "valid_pixels": 100,
        }
        for r in range(2)
        for c in range(2)
    ]
    result = coarsen(rows, 2)
    assert len(result) == 1
    assert result[0]["census_population"] == 40
    assert result[0]["ghsl_area"] == 20
    assert result[0]["built_share"] == pytest.approx(0.5)
    assert result[0]["grid_row"] == 0 and result[0]["grid_col"] == 0
    assert coarsen(rows[:-1], 2) == []


def test_coarsen_rejects_duplicate_mesh():
    row = {
        "mesh_code": "same",
        "grid_row": 0,
        "grid_col": 0,
        "census_population": 10,
        "ghsl_area": 5,
        "built_share": 0.5,
        "valid_pixels": 100,
    }
    with pytest.raises(ValueError, match="duplicate"):
        coarsen([row, row], 2)


def test_pearson_checks_constant_and_known_result():
    assert pearson([1, 2, 3], [3, 2, 1]) == pytest.approx(-1)
    with pytest.raises(ValueError, match="constant"):
        pearson([1, 1], [2, 3])
