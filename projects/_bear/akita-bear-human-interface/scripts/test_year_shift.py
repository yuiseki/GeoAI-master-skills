"""Known-answer tests for the year-shift rules."""

import interface_year_shift as ys


def test_the_common_axis_is_fitted_on_the_two_other_years():
    assert ys.axis_file(2025, 2026) == "b2_confirm_2023-2024_to_2025.npz"
    assert ys.axis_file(2023, 2024) == "axes_2025-2026.npz"
    assert ys.axis_file(2024, 2026) == "axes_2023-2025.npz"


def test_an_axis_moves_only_with_a_small_effect_and_a_block_swap_p_below_005():
    assert ys.direction(0.2, 0.01) == "higher"
    assert ys.direction(-0.2, 0.01) == "lower"
    assert ys.direction(0.1, 0.001) == "no clear move"
    assert ys.direction(0.3, 0.2) == "no clear move"


def test_reading_names_the_two_axis_combination():
    assert ys.reading("higher", "lower") == "toward higher bear-side proxy and lower human-side proxy"
    assert ys.reading("no clear move", "higher") == "bear-side: no clear move; human-side: higher"
