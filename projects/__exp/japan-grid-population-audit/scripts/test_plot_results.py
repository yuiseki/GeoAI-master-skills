"""uv run --no-project --with pytest python3 -m pytest -q projects/__exp/japan-grid-population-audit/scripts/test_plot_results.py"""

import pytest
from plot_results import paired_prefecture_points


def test_plot_uses_saved_pair_without_recalculating_recall():
    points = paired_prefecture_points(
        [
            {
                "prefecture": "13",
                "meshes": 20,
                "ghsl_area_recall10": 0.7,
                "ghsl_center_recall10": 0.4,
            }
        ]
    )
    assert points == [("13", 20, 0.4, 0.7)]
    with pytest.raises(ValueError, match="missing"):
        paired_prefecture_points(
            [{"prefecture": "13", "meshes": 20, "ghsl_area_recall10": 0.7}]
        )
