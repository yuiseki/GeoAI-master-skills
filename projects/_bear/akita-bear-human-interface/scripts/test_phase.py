"""Known-answer tests for the phase space, the year-shift statistics and the null shuffles."""

import numpy as np
import pytest

import phase as ph


def test_percentile_uses_average_ranks_over_all_cells():
    assert ph.percentile(np.array([0.1, 0.4, 0.4, 0.9])).tolist() == [0.25, 0.625, 0.625, 1.0]


def test_quintile_cuts_the_percentile_into_five_equal_bands():
    p = np.array([0.01, 0.2, 0.2001, 0.4, 0.6, 0.61, 0.8, 0.95, 1.0])
    assert ph.quintile(p).tolist() == [1, 1, 2, 2, 3, 4, 4, 5, 5]


def test_regions_follow_the_preregistered_table_and_cover_every_bin_once():
    want = {"bear_core": {(4, 1), (4, 2), (5, 1), (5, 2)},
            "contact": {(4, 4), (4, 5), (5, 4), (5, 5)},
            "boundary": {(3, 3), (3, 4), (4, 3)},
            "human_core": {(1, 4), (1, 5), (2, 4), (2, 5)},
            "low_both": {(1, 1), (1, 2), (2, 1), (2, 2)},
            "other": {(3, 1), (3, 2), (1, 3), (2, 3), (3, 5), (5, 3)}}
    got = {}
    for b in range(1, 6):
        for h in range(1, 6):
            got.setdefault(ph.region(b, h), set()).add((b, h))
    assert got == want


def test_bin_table_counts_cells_positives_rates_and_shares():
    bq = np.array([1, 1, 5, 5, 5])
    hq = np.array([1, 1, 5, 5, 1])
    pos = np.array([0, 1, 1, 1, 0], bool)
    t = {(r["b"], r["h"]): r for r in ph.bin_table(bq, hq, pos)}
    assert len(t) == 25
    assert t[(1, 1)] == {"b": 1, "h": 1, "region": "low_both", "n_cells": 2, "n_pos": 1, "rate": 0.5, "share": 1 / 3}
    assert t[(5, 5)]["n_pos"] == 2 and t[(5, 5)]["share"] == pytest.approx(2 / 3)
    assert t[(5, 1)]["rate"] == 0.0
    assert t[(3, 3)]["n_cells"] == 0 and t[(3, 3)]["rate"] is None


def test_region_shares_sum_the_bins():
    bq = np.array([5, 5, 1, 3])
    hq = np.array([5, 1, 5, 3])
    pos = np.array([1, 1, 1, 1], bool)
    s = ph.region_shares(bq, hq, pos)
    assert s == {"bear_core": 0.25, "contact": 0.25, "boundary": 0.25, "human_core": 0.25, "low_both": 0.0, "other": 0.0}


def test_cliffs_delta_is_positive_when_the_later_year_is_higher():
    assert ph.cliffs_delta(np.array([3, 4]), np.array([1, 2])) == 1.0
    assert ph.cliffs_delta(np.array([1, 2]), np.array([3, 4])) == -1.0
    assert ph.cliffs_delta(np.array([1, 2]), np.array([1, 2])) == 0.0


def test_jsd_is_zero_for_equal_and_one_for_disjoint_compositions():
    assert ph.jsd([1, 1, 0], [2, 2, 0]) == pytest.approx(0.0)
    assert ph.jsd([1, 0], [0, 1]) == pytest.approx(1.0)


def test_summary_gives_quartiles():
    s = ph.summary(np.array([0.0, 0.25, 0.5, 0.75, 1.0]))
    assert s == {"n": 5, "q1": 0.25, "median": 0.5, "q3": 0.75}


def test_block_shuffle_moves_whole_block_patterns_and_drops_cells_landing_outside():
    # a 4 x 2 grid of cells in two 2 x 2 blocks; the right block lacks its top-right cell
    ix = np.array([0, 1, 0, 1, 2, 2, 3])
    iy = np.array([0, 0, 1, 1, 0, 1, 1])
    pos = np.array([1, 0, 0, 1, 0, 0, 0], bool)  # left block: (0,0) and (1,1)
    out = ph.block_shuffle(ix, iy, pos, size=2, perm={(0, 0): (1, 0), (1, 0): (0, 0)})
    # (0,0) -> (2,0) kept; (1,1) -> (3,1) kept
    assert out.tolist() == [False, False, False, False, True, False, True]
    pos2 = np.array([1, 1, 0, 0, 0, 0, 0], bool)  # (1,0) -> (3,0), which is not a cell
    out2 = ph.block_shuffle(ix, iy, pos2, size=2, perm={(0, 0): (1, 0), (1, 0): (0, 0)})
    assert out2.tolist() == [False, False, False, False, True, False, False]


def test_random_block_perm_is_a_permutation_of_the_blocks():
    blocks = [(0, 0), (1, 0), (0, 1), (5, 5)]
    perm = ph.random_block_perm(blocks, np.random.default_rng(0))
    assert sorted(perm) == sorted(blocks) and sorted(perm.values()) == sorted(blocks)


def test_block_swap_exchanges_the_year_labels_of_whole_blocks():
    block = np.array([0, 0, 1, 1])
    a = np.array([1, 0, 1, 0], bool)
    b = np.array([0, 1, 0, 1], bool)
    na, nb = ph.block_swap(a, b, block, swap={0: True, 1: False})
    assert na.tolist() == [False, True, True, False]
    assert nb.tolist() == [True, False, False, True]


def test_block_flip_flips_whole_blocks():
    out = ph.block_flip([True, False, True, False], [7, 7, 9, 9], [True, False])
    assert out.tolist() == [False, True, True, False]


def test_pair_stats_sees_a_shift_up_the_bear_axis_only():
    pb = np.array([0.1, 0.2, 0.9, 0.95])
    ph_ = np.array([0.5, 0.5, 0.5, 0.5])
    later = np.array([False, False, True, True])
    s = ph.pair_stats(pb, ph_, later, ph.quintile(pb), ph.quintile(ph_))
    assert s["cliff_b"] == 1.0 and s["cliff_h"] == 0.0 and s["jsd"] == pytest.approx(1.0)
