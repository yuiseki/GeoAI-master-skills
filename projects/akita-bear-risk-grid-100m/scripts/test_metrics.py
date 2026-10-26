import numpy as np

import metrics as mt


def test_capture_of_a_perfect_score_is_all_positives_when_they_fit_in_the_top():
    pos = np.zeros(100, dtype=bool)
    pos[:3] = True
    score = pos.astype(float)
    assert mt.capture(mt.rank_order(score), pos, 0.05) == 1.0


def test_capture_counts_the_cell_straddling_the_cut_by_its_fraction():
    # 10 cells, top 15% = 1.5 cells: the first cell whole and half of the second
    pos = np.array([True, True] + [False] * 8)
    order = mt.rank_order(np.arange(10)[::-1].astype(float))
    assert np.isclose(mt.capture(order, pos, 0.15), (1 + 0.5) / 2)


def test_rank_order_breaks_ties_by_the_second_key_then_at_random():
    s = np.array([1.0, 1.0, 1.0, 0.0])
    second = np.array([0.0, 2.0, 1.0, 9.0])
    assert list(mt.rank_order(s, second)[:3]) == [1, 2, 0]
    # a score with all cells tied gives, on average, the share of the cut
    pos = np.zeros(1000, dtype=bool)
    pos[:100] = True
    caps = [mt.capture(mt.rank_order(np.zeros(1000), seed=k), pos, 0.05) for k in range(50)]
    assert abs(np.mean(caps) - 0.05) < 0.01


def test_weighted_capture_matches_duplicating_cells():
    rng = np.random.default_rng(0)
    score = rng.random(50)
    pos = rng.random(50) < 0.3
    w = rng.integers(0, 3, size=50).astype(float)
    order = mt.rank_order(score)
    dup = np.repeat(np.arange(50), w.astype(int))
    order_d = mt.rank_order(score[dup])
    a = mt.capture(order, pos, 0.1, weights=w)
    b = mt.capture(order_d, pos[dup], 0.1)
    assert np.isclose(a, b)


def test_block_bootstrap_interval_contains_zero_for_identical_scores_and_excludes_it_for_a_clear_win():
    rng = np.random.default_rng(1)
    n = 4000
    blocks = np.repeat(np.arange(40), n // 40)
    pos = rng.random(n) < 0.05
    good = pos + rng.normal(0, 0.3, n)
    bad = rng.normal(0, 1, n)
    lo, hi, _ = mt.bootstrap_diff(mt.rank_order(good), mt.rank_order(bad), pos, blocks, 0.05, B=200, seed=0)
    assert lo > 0
    lo, hi, _ = mt.bootstrap_diff(mt.rank_order(good), mt.rank_order(good), pos, blocks, 0.05, B=50, seed=0)
    assert lo <= 0 <= hi


def test_capture_with_counts_gives_the_share_of_the_reports():
    counts = np.array([5.0, 0, 1, 0])
    order = mt.rank_order(np.array([4.0, 3, 2, 1]))
    assert np.isclose(mt.capture(order, counts, 0.25), 5 / 6)
