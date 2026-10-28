"""Known-answer tests for Akita-city fixed-score percentile auditing."""

import numpy as np
import pytest

import akita_fixed_score_percentile as audit


def test_city_rank_percentile_top_sets_and_deciles_are_fixed():
    rank, percentile, decile = audit.city_rank(np.arange(20, 0, -1, dtype=float))
    assert rank.tolist() == list(range(20))
    assert percentile[0] == pytest.approx(.975)
    assert percentile[-1] == pytest.approx(.025)
    assert decile[[0, 1, 2, 19]].tolist() == [1, 1, 2, 10]
    positive = np.zeros(20, dtype=bool)
    positive[[0, 1, 10, 11]] = True
    result = audit.summarize_positive(positive, rank, percentile, decile)
    assert result["n_positive"] == 4
    assert result["percentile"]["median"] == pytest.approx(.7)
    assert result["top_share"]["1%"] == .25
    assert result["top_share"]["5%"] == .25
    assert result["top_share"]["10%"] == .5
    assert result["deciles"][0]["n_positive"] == 2
    assert sum(row["n_positive"] for row in result["deciles"]) == 4


def test_later_lower_scores_have_negative_cliff_and_top_increases():
    rank, percentile, decile = audit.city_rank(np.arange(20, 0, -1, dtype=float))
    y25 = np.zeros(20, dtype=bool)
    y26 = np.zeros(20, dtype=bool)
    y25[[0, 1, 10, 11]] = True
    y26[[8, 9, 18, 19]] = True
    result = audit.compare_years(y25, y26, rank, percentile, decile)
    assert result["cliffs_delta_2026_minus_2025"] < 0
    assert result["ks_statistic"] > 0
    assert {row["decile"] for row in result["largest_decile_share_increases"][:2]} == {"D5", "D10"}


def test_empty_positive_or_misalignment_rejected():
    rank, percentile, decile = audit.city_rank([.2, .1])
    with pytest.raises(ValueError, match="positive"):
        audit.summarize_positive(np.array([False, False]), rank, percentile, decile)
    with pytest.raises(ValueError, match="aligned"):
        audit.summarize_positive(np.array([True]), rank, percentile, decile)
