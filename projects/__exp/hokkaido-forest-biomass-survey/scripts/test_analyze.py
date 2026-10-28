"""Synthetic checks for area overlay and candidate selection."""

from shapely.geometry import box

from analyze import overlap_records, ranked_ids


def test_strtree_overlay_matches_known_rectangles_and_uncovered():
    cells = [(1, 1, box(0, 0, 2, 2)), (2, 1, box(3, 0, 5, 2))]
    types = [(1, 2, box(0, 0, 1, 2)), (2, 6, box(1, 0, 2, 2))]
    rows, centers = overlap_records(cells, types)
    assert rows[(1, 1)] == (4.0, 4.0, 2.0, 2)
    assert rows[(2, 1)] == (4.0, 0.0, 0.0, 0)
    assert centers[(1, 1)] == [2, 6]
    assert centers[(2, 1)] == []


def test_rank_never_turns_unknown_coverage_into_nonforest():
    records = [
        {"cell_row": 1, "cell_col": 1, "drop": 20, "cover_frac": 1.0, "forest_frac": 0.9,
         "valid_pixels_2010": 100, "valid_pixels_2025": 100, "uncertainty_mean_2025_mg_ha": 3},
        {"cell_row": 2, "cell_col": 1, "drop": 30, "cover_frac": 0.0, "forest_frac": 0.0,
         "valid_pixels_2010": 100, "valid_pixels_2025": 100, "uncertainty_mean_2025_mg_ha": 3},
        {"cell_row": 3, "cell_col": 1, "drop": 10, "cover_frac": 1.0, "forest_frac": 0.6,
         "valid_pixels_2010": 100, "valid_pixels_2025": 100, "uncertainty_mean_2025_mg_ha": 2},
    ]
    assert ranked_ids(records, 2, forest_min=0.8) == [(1, 1)]
    assert ranked_ids(records, 2, forest_min=0.5) == [(1, 1), (3, 1)]


def test_rank_requires_positive_drop_and_breaks_ties_by_id():
    records = [
        {"cell_row": 2, "cell_col": 1, "drop": 4, "cover_frac": 1, "forest_frac": 1,
         "valid_pixels_2010": 100, "valid_pixels_2025": 100, "uncertainty_mean_2025_mg_ha": 8},
        {"cell_row": 1, "cell_col": 1, "drop": 4, "cover_frac": 1, "forest_frac": 1,
         "valid_pixels_2010": 100, "valid_pixels_2025": 100, "uncertainty_mean_2025_mg_ha": 2},
        {"cell_row": 3, "cell_col": 1, "drop": -4, "cover_frac": 1, "forest_frac": 1,
         "valid_pixels_2010": 100, "valid_pixels_2025": 100, "uncertainty_mean_2025_mg_ha": 1},
    ]
    assert ranked_ids(records, 2) == [(1, 1), (2, 1)]
    assert ranked_ids(records, 2, uncertainty_cap=5) == [(1, 1)]
