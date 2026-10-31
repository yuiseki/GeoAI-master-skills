"""Known-answer tests for the role permutation (F1)."""

import interface_role_perm as rp


def test_random_split_keeps_sizes_order_and_every_feature_once():
    pool = list("abcdefghij")
    h1, h2 = rp.random_split(pool, 4, seed=3)
    assert len(h1) == 4 and len(h2) == 6
    assert sorted(h1 + h2) == pool
    assert h1 == sorted(h1, key=pool.index) and h2 == sorted(h2, key=pool.index)
    assert rp.random_split(pool, 4, seed=3) == (h1, h2)


def test_rank_of_real_counts_ties_against_the_real_split_and_reverses_for_spearman():
    perms = [{"jsd": 0.1, "spearman": 0.5}, {"jsd": 0.3, "spearman": 0.2}, {"jsd": 0.2, "spearman": 0.9}]
    real = {"jsd": 0.2, "spearman": 0.2}
    assert rp.rank_of_real(real, perms, "jsd") == 3  # 0.3 and the tie 0.2 are at least as large
    assert rp.rank_of_real(real, perms, "spearman") == 2  # the tie 0.2 is at most as small
