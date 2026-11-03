"""Tests of rank.py on cases whose answer is known.

uvx --with numpy --with scipy --with pytest pytest -q scripts/test_rank.py
"""
import math

import numpy as np
import pytest

from rank import break_2seg, hypergeom_tail, rank_order, recall_at, tile_xy


def test_tile_xy_matches_the_site_tile():
    # the requester's point is in z16 tile (58289, 25820), z17 (116579, 51641)
    assert tile_xy(140.1949078559463, 35.61884481509456, 16) == (58289, 25820)
    assert tile_xy(140.1949078559463, 35.61884481509456, 17) == (116579, 51641)


def test_tile_xy_vectorised_and_edges():
    x, y = tile_xy(np.array([-180.0, 0.0]), np.array([0.0, 0.0]), 1)
    assert list(x) == [0, 1] and list(y) == [1, 1]


def test_rank_order_breaks_ties_by_id():
    ids = ["b", "a", "c"]
    assert rank_order([1.0, 1.0, 2.0], ids) == ["c", "a", "b"]


def test_recall_at():
    ids = list("abcdef")
    scores = [6, 5, 4, 3, 2, 1]
    pos = {"a", "d"}
    assert recall_at(scores, ids, pos, 2) == 0.5
    assert recall_at(scores, ids, pos, 4) == 1.0
    with pytest.raises(ValueError):
        recall_at(scores, ids, set(), 2)


def test_hypergeom_tail_against_counting():
    # 10 items, 3 positive, draw 4: P(at least 2 positives) by counting
    N, K, n = 10, 3, 4
    want = sum(math.comb(K, k) * math.comb(N - K, n - k) for k in range(2, 4)) / math.comb(N, n)
    assert abs(hypergeom_tail(2, N, K, n) - want) < 1e-12
    assert hypergeom_tail(0, N, K, n) == pytest.approx(1.0)


def test_break_2seg_finds_a_step():
    rng = np.random.default_rng(0)
    t = np.arange(60)
    y = np.where(t < 37, 0.0, 3.0)[:, None] + rng.normal(0, 0.3, (60, 2))
    k, sse = break_2seg(y, min_seg=5)
    assert k == 37
    assert len(sse) == 60 and np.isnan(sse[:5]).all() and np.isfinite(sse[5:56]).all()


def test_break_2seg_respects_min_seg():
    y = np.zeros((20, 1))
    y[-2:] = 10.0  # a step too close to the end
    k, _ = break_2seg(y, min_seg=5)
    assert 5 <= k <= 15
