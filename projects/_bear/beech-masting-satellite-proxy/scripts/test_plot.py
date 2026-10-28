"""Tests for the figure rows (they come from the block outputs unchanged)."""

import pandas as pd

import plot


def test_model_rows_pair_development_and_confirmation():
    b2 = {"C": {"scores": {m: {"within_year_spearman": i / 10} for i, m in enumerate(plot.MODELS)}}}
    b3 = {"schemes": {"C": {"scores": {m: {"within_year_spearman": 1 + i / 10} for i, m in enumerate(plot.MODELS)}}}}
    rows = plot.model_rows(b2, b3, "C")
    assert rows[0] == ("B0", 0.0, 1.0) and rows[-1] == ("RS2", 0.4, 1.4)


def test_site_coverage_is_share_of_years():
    cov = pd.DataFrame({"ID": [1, 1, 2, 2], "t": [1990, 1991] * 2, "prev_summer": [1, 0, 2, 3],
                        "current_spring": [0, 0, 1, 0]})
    sc = plot.site_coverage(cov)
    assert sc.loc[1, "ps"] == 0.5 and sc.loc[2, "ps"] == 1.0 and sc.loc[2, "cs"] == 0.5
