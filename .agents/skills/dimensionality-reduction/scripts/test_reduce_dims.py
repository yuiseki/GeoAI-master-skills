"""uvx --with numpy --with scipy --with duckdb --with pytest pytest test_reduce_dims.py"""

import numpy as np

from reduce_dims import bootstrap_congruence, match_congruence, parallel_analysis, pca


def two_factors(n=400, seed=0, second=1.0):
    rng = np.random.default_rng(seed)
    f = rng.normal(size=(n, 2))
    load = np.zeros((2, 10))
    load[0, :5] = 1.0
    load[1, 5:] = second
    return f @ load + rng.normal(scale=0.6, size=(n, 10))


def test_parallel_analysis_keeps_the_true_number_of_factors():
    keep, _, _ = parallel_analysis(two_factors(), permutations=100, seed=0)
    assert keep == 2


def test_parallel_analysis_keeps_nothing_in_noise():
    X = np.random.default_rng(1).normal(size=(400, 10))
    keep, _, _ = parallel_analysis(X, permutations=100, seed=0)
    assert keep == 0


def test_features_are_standardised():
    # One noise column on a huge scale would be the first component without standardisation.
    X = two_factors()
    X = np.c_[X, np.random.default_rng(2).normal(scale=1000, size=len(X))]
    _, loadings, _ = pca(X)
    assert abs(loadings[0, -1]) < 0.2


def test_bootstrap_congruence_is_high_for_distinct_factors_and_low_for_noise():
    c = bootstrap_congruence(two_factors(second=0.6), components=4, resamples=50, seed=0)
    assert c["axis"][0] > 0.97 and c["axis"][1] > 0.97
    # Matching each axis to its best resampled partner lifts noise axes too (0.64 to 0.91 over
    # four seeds); they stay below the usual 0.95 bar for "the same axis".
    assert c["axis"][2] < 0.95 and c["axis"][3] < 0.95


def test_equal_factors_rotate_within_a_stable_subspace():
    # With two factors of the same strength, any rotation of PC1 and PC2 within their plane
    # explains the same variance, so the single axes wander between resamples while the plane
    # they span stays put.
    c = bootstrap_congruence(two_factors(), components=2, resamples=50, seed=3)
    assert min(c["axis"]) < 0.95
    assert min(c["subspace"]) > 0.98


def test_axes_are_matched_by_order_and_sign():
    # Distinct factors: PC1 and PC2 keep their order, but the sign of a component is arbitrary.
    # Matched properly, both stay near 1.
    c = bootstrap_congruence(two_factors(second=0.6), components=2, resamples=50, seed=4)
    assert min(c["axis"]) > 0.95


def test_matching_ignores_order_and_sign():
    rng = np.random.default_rng(5)
    ref = np.linalg.qr(rng.normal(size=(8, 3)))[0].T  # three orthonormal loading vectors
    cand = np.array([-ref[2], ref[0], -ref[1]])
    assert np.allclose(match_congruence(ref, cand), 1.0)


def blocks(rng, n, corr=0.0):
    """Factor 1 on features 0-6, factor 2 on features 7-9 (so they differ in strength after
    standardising), with the two factors correlated by corr."""
    f = rng.multivariate_normal([0, 0], [[1, corr], [corr, 1]], size=n)
    X = np.c_[np.repeat(f[:, :1], 7, axis=1), np.repeat(f[:, 1:], 3, axis=1)]
    return X + rng.normal(scale=0.5, size=X.shape)


def test_the_same_structure_compares_as_the_same_axes():
    from reduce_dims import compare_subspaces

    rng = np.random.default_rng(20)
    c = compare_subspaces(blocks(rng, 3000), blocks(rng, 3000), 2)
    assert min(c["axis"]) > 0.98 and min(c["in_subspace"]) > 0.98


def test_axes_turned_within_the_same_plane_are_told_apart_from_a_new_plane():
    from reduce_dims import compare_subspaces

    rng = np.random.default_rng(21)
    a = blocks(rng, 3000)
    # Correlated factors: the leading component mixes both blocks, so it turns within their plane.
    c = compare_subspaces(a, blocks(rng, 3000, corr=0.9), 2)
    assert c["axis"][0] < 0.95
    assert min(c["in_subspace"]) > 0.95
    # A structure along a contrast inside each block lies outside that plane.
    v = np.array([1, -1, 1, -1, 1, -1, 1, 1, -1, 1], float)
    other = (rng.normal(size=(3000, 1)) * 3) @ v[None, :] + rng.normal(size=(3000, 10))
    c2 = compare_subspaces(a, other, 2)
    assert c2["in_subspace"][0] < 0.3


def test_scores_on_the_reference_axes_show_a_shift():
    from reduce_dims import compare_subspaces

    rng = np.random.default_rng(22)
    a = blocks(rng, 3000)
    later = a + 2.0  # every feature up by the same amount
    c = compare_subspaces(a, later, 2)
    assert abs(c["score_shift"][0]) > 0.5
    assert abs(compare_subspaces(a, a, 2)["score_shift"][0]) < 1e-9
