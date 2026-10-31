# uvx --with pytest --with numpy pytest scripts/test_listing.py -q
import numpy as np
import pytest

from listing import block_bootstrap, diff_share, grid_blocks, share, verdict, verdict_below


def test_grid_blocks_groups_by_cell():
    ids = grid_blocks([0, 1999, 2000, 0], [0, 10, 0, -1])
    assert ids[0] == ids[1] and ids[0] != ids[2] and ids[0] != ids[3]


def test_share_and_diff():
    assert share([1, 0, 0, 1]) == 0.5
    assert diff_share([1, 1, 0, 0], [1, 1, 1, 0]) == pytest.approx(2 / 3)
    assert np.isnan(share([]))


def test_block_bootstrap_keeps_blocks_whole():
    # two blocks: one all ones, one all zeros; any resample is 0, 0.5 or 1, never anything between
    blocks = np.array([0, 0, 0, 1, 1, 1])
    y = np.array([1, 1, 1, 0, 0, 0])
    seen = set()
    lo, hi, n = block_bootstrap(blocks, lambda i: (seen.add(round(y[i].mean(), 3)), y[i].mean())[1], n=200)
    assert seen <= {0.0, 0.5, 1.0} and n == 200 and lo == 0.0 and hi == 1.0


def test_block_bootstrap_drops_nan():
    lo, hi, n = block_bootstrap(np.array([0, 1]), lambda i: np.nan if len(set(i)) == 1 else 1.0, n=100)
    assert n < 100 and lo == hi == 1.0


def test_verdicts():
    assert verdict(0.1, 0.3, 0) == "支持" and verdict(-0.2, 0.0, 0) == "退ける" and verdict(-0.1, 0.2, 0) == "判定できない"
    assert verdict_below(0.2, 0.4, 0.5) == "支持" and verdict_below(0.5, 0.7, 0.5) == "退ける"
    assert verdict_below(0.4, 0.6, 0.5) == "判定できない"
