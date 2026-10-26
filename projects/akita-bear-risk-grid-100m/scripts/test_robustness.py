import numpy as np

import robustness as rb


def test_coarsen_labels_any_positive_and_probabilities_as_one_minus_product():
    ix = np.array([0, 1, 2, 3])
    iy = np.array([0, 0, 0, 0])
    pos = np.array([False, True, False, False])
    p = np.array([0.1, 0.2, 0.5, 0.0])
    lab, sc, n = rb.coarsen(ix, iy, pos, p, factor=2, how="prob")
    order = np.argsort(np.unique((ix // 2) * 100000 + iy // 2))
    assert list(lab[order]) == [True, False]
    assert np.allclose(sc[order], [1 - 0.9 * 0.8, 1 - 0.5 * 1.0])
    assert list(n[order]) == [2, 2]


def test_coarsen_density_scores_by_the_mean():
    ix = np.array([0, 1, 2])
    iy = np.array([0, 0, 0])
    lab, sc, n = rb.coarsen(ix, iy, np.zeros(3, bool), np.array([2.0, 4.0, 9.0]), factor=2, how="mean")
    assert sorted(sc.tolist()) == [3.0, 9.0]
