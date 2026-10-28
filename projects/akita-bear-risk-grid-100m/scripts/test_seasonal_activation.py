"""Known-answer tests for the within-season activation score."""

import numpy as np
import pytest

import metrics as mt
import seasonal_activation as sa


def test_disk_kernel_counts_cell_centres_within_the_radius():
    k = sa.disk_kernel(100, 100)
    assert k.shape == (3, 3)
    assert k.sum() == 5  # the centre and its four neighbours; diagonals are 141 m away
    assert sa.disk_kernel(50, 100).sum() == 1
    assert sa.disk_kernel(1000, 100).sum() == 317  # lattice points in a circle of radius 10


def test_activity_counts_reports_near_each_cell_as_integers():
    counts = np.zeros((7, 7))
    counts[3, 3] = 2
    counts[0, 0] = 1
    act = sa.activity(counts, sa.disk_kernel(100, 100))
    assert act.dtype == np.int32
    assert act[3, 3] == 2 and act[3, 4] == 2 and act[4, 4] == 0
    assert act[0, 0] == 1 and act[0, 1] == 1 and act[1, 1] == 0
    assert act.sum() == 2 * 5 + 1 * 3  # the corner loses the neighbours off the grid


def test_mondays_cover_whole_weeks_from_may_to_the_end_of_september():
    t = sa.week_origins(2026)
    assert str(t[0]) == "2026-05-04" and str(t[-1]) == "2026-09-21"
    assert all(np.diff(t).astype(int) == 7)
    t25 = sa.week_origins(2025)
    assert str(t25[0]) == "2025-05-05" and str(t25[-1]) == "2025-09-22"


def test_take_fraction_reproduces_metrics_capture():
    rng = np.random.default_rng(1)
    score = rng.random(203)
    pos = rng.random(203) < .2
    order = mt.rank_order(score, seed=0)
    take = sa.take_fraction(order, .05)
    assert take.sum() == pytest.approx(.05 * 203)
    assert (take * pos).sum() / pos.sum() == pytest.approx(mt.capture(order, pos, .05))


def test_mixed_score_multiplies_susceptibility_by_smoothed_activity():
    env = np.array([.5, .1, .1])
    act = np.array([0, 4, 0])
    assert sa.mixed(env, act, 1).tolist() == pytest.approx([.5, .5, .1])
    with pytest.raises(ValueError):
        sa.mixed(env, act, 0)


def test_pooled_capture_and_block_interval():
    # two weeks, four cells in two blocks; fixed takes
    takes = [np.array([1., 0, 0, 0]), np.array([0, 1., 0, 0])]
    pos = [np.array([1, 0, 1, 0], bool), np.array([0, 1, 0, 0], bool)]
    blocks = np.array([0, 0, 1, 1])
    hit, n = sa.by_block(takes, pos, blocks)
    assert hit.tolist() == [2, 0] and n.tolist() == [2, 1]
    assert sa.pooled(hit, n) == pytest.approx(2 / 3)
    lo, hi = sa.block_interval(hit, hit * 0, n, B=200, seed=0)
    assert 0 <= lo <= hi <= 1 and hi == 1  # a resample of block 0 alone captures all
    lo, hi = sa.block_interval(hit, hit, n, B=50, seed=0)
    assert lo == hi == 0


def test_choose_prefers_the_best_then_the_smaller_radius_and_larger_alpha():
    rows = [{"r": 1000, "alpha": .3, "capture": .6}, {"r": 500, "alpha": .3, "capture": .6},
            {"r": 500, "alpha": 1, "capture": .6}, {"r": 2000, "alpha": 3, "capture": .5}]
    assert sa.choose(rows) == {"r": 500, "alpha": 1, "capture": .6}
