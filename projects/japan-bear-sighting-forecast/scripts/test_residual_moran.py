import numpy as np

import residual_moran as r


def line_W(m):
    W = np.zeros((m, m))
    for i in range(m - 1):
        W[i, i + 1] = W[i + 1, i] = 1.0
    return W / W.sum(axis=1, keepdims=True)


def test_morans_i_is_positive_for_clustered_values_negative_for_alternating_and_nan_for_constant():
    W = line_W(10)
    clustered = np.array([5, 5, 5, 5, 5, -5, -5, -5, -5, -5], dtype=float)
    alternating = np.array([5, -5] * 5, dtype=float)
    assert r.morans_i(clustered, W) > 0.5
    assert r.morans_i(alternating, W) < -0.5
    assert np.isnan(r.morans_i(np.ones(10), W))


def test_morans_i_matches_a_hand_computed_value():
    # three in a row, values 1, 0, -1 (mean 0); W: ends have one neighbour (the middle), middle has both (0.5 each)
    W = np.array([[0, 1, 0], [0.5, 0, 0.5], [0, 1, 0]])
    x = np.array([1.0, 0.0, -1.0])
    # I = (n / S0) * sum_ij w_ij z_i z_j / sum z^2; S0 = 3; sum w z z = 0 (the middle z is 0) -> I = 0
    assert r.morans_i(x, W) == 0.0
