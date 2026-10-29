"""Known-answer tests for the one-shot Akita City activation check on 2024."""

import numpy as np
import pytest

import akita_city_activation_2024 as ac


def test_within_take_selects_the_top_share_of_the_masked_cells_only():
    score = np.array([.9, .8, .7, .6, .5, .4, .3, .2, .1, 0.])
    mask = np.array([0, 1, 0, 1, 1, 1, 0, 0, 0, 0], bool)
    take = ac.within_take(score, mask, .5)
    assert take.tolist() == [0, 1, 0, 1, 0, 0, 0, 0, 0, 0]
    take = ac.within_take(score, mask, .3)  # 1.2 of 4 cells: the next one by its fraction
    assert take.tolist() == pytest.approx([0, 1, 0, .2, 0, 0, 0, 0, 0, 0])


def test_blocks_touching_keeps_only_blocks_with_a_masked_cell():
    blocks = np.array([7, 7, 3, 3, 5])
    mask = np.array([0, 1, 0, 0, 1], bool)
    ids, keep = ac.blocks_touching(blocks, mask)
    assert ids.tolist() == [3, 5, 7] and keep.tolist() == [False, True, True]


def test_decision_needs_a_positive_lower_bound():
    assert ac.decision([.02, .001, .04])["supported"] is True
    assert ac.decision([.02, -.001, .04])["supported"] is False
