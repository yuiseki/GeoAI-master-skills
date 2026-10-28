from plot import classify_sets


def test_plot_categories_do_not_duplicate_points():
    summary = {
        "variants": {
            "raw": [{"cell_row": 1, "cell_col": 1}, {"cell_row": 2, "cell_col": 1}],
            "forest_0_8_main": [{"cell_row": 2, "cell_col": 1}, {"cell_row": 3, "cell_col": 1}],
        },
        "stable_main_ids": [{"cell_row": 3, "cell_col": 1}],
    }
    categories = classify_sets(summary)
    assert categories["stable"] == {(3, 1)}
    assert categories["main_other"] == {(2, 1)}
    assert categories["raw_only"] == {(1, 1)}
