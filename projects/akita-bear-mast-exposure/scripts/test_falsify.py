"""Tests for the two permutations."""

import numpy as np

import falsify as fz


def test_year_permutations_are_all_24_with_identity_first():
    p = fz.year_permutations({2023: 4.9, 2024: 2.4, 2025: 5.0, 2026: 1.8})
    assert len(p) == 24 and p[0] == {2023: 4.9, 2024: 2.4, 2025: 5.0, 2026: 1.8}
    assert len({tuple(sorted(x.items())) for x in p}) == 24


def test_tiles_donors_are_mostly_inside():
    inside = np.zeros((25, 20), bool)
    inside[:20, :10] = True  # two full 10x10 tiles stacked, plus a half-inside row of tiles
    inside[20:25, :10] = True
    donors, targets = fz.tiles(inside, size=10, min_share=0.9)
    assert donors == [(0, 0), (1, 0)]
    assert (2, 0) in targets and (0, 1) not in targets


def test_tile_permutation_moves_whole_tiles():
    f = np.arange(400, dtype=float).reshape(20, 20)
    inside = np.ones((20, 20), bool)
    rng = np.random.default_rng(0)
    g = fz.permute_tiles(f, inside, rng, size=10, min_share=0.9)
    blocks = sorted(g[i:i + 10, j:j + 10].sum() for i in (0, 10) for j in (0, 10))
    assert blocks == sorted(f[i:i + 10, j:j + 10].sum() for i in (0, 10) for j in (0, 10))
    assert np.array_equal(g[0:10, 0:10] - g[0, 0], f[0:10, 0:10] - f[0, 0])  # the inside of a tile keeps its pattern
