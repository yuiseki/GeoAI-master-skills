"""Known-answer tests for the trial-and-error maps."""

import numpy as np

import trial_maps as tm


def test_top_set_takes_the_first_ceiling_of_k_cells_by_score():
    score = np.array([.1, .9, .5, .7, .3])
    assert tm.top_set(score, .4).tolist() == [False, True, False, True, False]
    assert tm.top_set(score, .3).tolist() == [False, True, False, True, False]  # ceil(1.5) = 2
    assert tm.top_set(score, .2).tolist() == [False, True, False, False, False]


def test_hit_miss_splits_positive_cells_by_the_top_set():
    pos = np.array([1, 1, 0, 1], bool)
    top = np.array([1, 0, 1, 0], bool)
    hit, miss = tm.hit_miss(pos, top)
    assert hit.tolist() == [True, False, False, False]
    assert miss.tolist() == [False, True, False, True]


def test_selection_change_separates_kept_added_and_dropped_cells():
    e = np.array([1, 1, 0, 0], bool)
    m = np.array([1, 0, 1, 0], bool)
    kept, added, dropped = tm.selection_change(e, m)
    assert kept.tolist() == [True, False, False, False]
    assert added.tolist() == [False, False, True, False]
    assert dropped.tolist() == [False, True, False, False]


def test_busiest_week_picks_the_most_positives_and_the_earliest_on_a_tie():
    assert tm.busiest_week([3, 7, 7, 1]) == 1


def test_block_net_sums_added_minus_dropped_per_block_and_pads_the_edge():
    inside = np.ones((3, 5), bool)
    inside[0, 0] = False
    added = np.zeros(14, bool)
    dropped = np.zeros(14, bool)
    added[0] = True  # row 0, column 1
    dropped[[1, 4]] = True  # row 0 columns 2 and 0 of row 1
    net = tm.block_net(inside, added, dropped, 2)
    assert net.shape == (2, 3)
    assert net.tolist() == [[0, -1, 0], [0, 0, 0]]
