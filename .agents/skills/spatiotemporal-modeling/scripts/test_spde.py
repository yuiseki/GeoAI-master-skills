"""uvx --with numpy --with scipy --with pytest pytest test_spde.py"""

import numpy as np
import pytest

from spde import covariance_column, krige, laplacian, matern_nu1, precision, tau_for

KAPPA = 10.0  # practical range sqrt(8) / 10 = 0.28


def test_the_laplacian_by_hand_on_a_three_by_one_strip():
    L = laplacian(3, 1, 1.0).toarray()
    np.testing.assert_allclose(L, [[-1, 1, 0], [1, -2, 1], [0, 1, -1]])  # zero-flux ends; rows sum to 0


def test_the_field_far_from_the_edges_has_the_matern_covariance():
    # A 2 x 2 domain with cells of 0.02 (h kappa = 0.2): at the centre, the variance and the correlations at 0.1,
    # 0.2 and 0.4 agree with sigma^2 kappa d K_1(kappa d) (measured: variance 1.023, ratios 1.000-1.002).
    n, h = 101, 0.02
    Q = precision(n, n, h, KAPPA, tau_for(1.0, KAPPA))
    centre = (n // 2) * n + n // 2
    col = covariance_column(Q, centre)
    assert col[centre] == pytest.approx(1.0, abs=0.04)
    for d in (0.1, 0.2, 0.4):
        j = centre + int(round(d / h))
        assert col[j] == pytest.approx(matern_nu1(d, 1.0, KAPPA), rel=0.02)


def test_the_discretisation_error_shrinks_with_the_cell():
    var = []
    for h in (0.04, 0.02, 0.01):
        n = int(round(2 / h)) + 1
        c = (n // 2) * n + n // 2
        var.append(covariance_column(precision(n, n, h, KAPPA, tau_for(1.0, KAPPA)), c)[c])
    err = np.abs(np.array(var) - 1)
    assert err[0] > err[1] > err[2]  # measured 0.063, 0.023, 0.008


def test_zero_flux_edges_double_the_variance_at_an_edge_and_quadruple_it_at_a_corner():
    n, h = 101, 0.02
    Q = precision(n, n, h, KAPPA, tau_for(1.0, KAPPA))
    edge, corner = (n // 2) * n, 0
    assert covariance_column(Q, edge)[edge] == pytest.approx(2.0, rel=0.03)
    assert covariance_column(Q, corner)[corner] == pytest.approx(4.0, rel=0.05)


def test_kriging_one_noiseless_observation_gives_the_covariance_shape():
    # One observation y at the centre with tiny noise: the posterior mean elsewhere is y C(d) / C(0).
    n, h = 81, 0.025
    Q = precision(n, n, h, KAPPA, tau_for(1.0, KAPPA))
    c = (n // 2) * n + n // 2
    col = covariance_column(Q, c)
    out = krige(Q, np.array([c]), np.array([2.0]), 1e-8)
    np.testing.assert_allclose(out["mean"], 2.0 * col / col[c], rtol=1e-5, atol=1e-8)


def test_padding_restores_the_interior_prediction_near_a_window_edge():
    # Observations on the left half of a window; the prediction at the window's left edge. With the grid ending
    # at the window, the zero-flux edge doubles the prior variance there and pulls the prediction off; with a
    # padding of two ranges the prediction matches a much larger grid's.
    rng = np.random.default_rng(0)
    h, pad = 0.02, 30  # 30 cells = 0.6, about two practical ranges

    def run(margin):
        n = 51 + 2 * margin
        Q = precision(n, n, h, KAPPA, tau_for(1.0, KAPPA))
        rows = margin + rng_rows
        cols = margin + rng_cols
        out = krige(Q, rows * n + cols, y, 0.01, variance_cells=[(margin + 25) * n + margin])
        return out["mean"][(margin + 25) * n + margin], out["variance"][0]

    rng_rows, rng_cols = rng.integers(0, 51, 40), rng.integers(0, 25, 40)
    y = rng.normal(size=40)
    m0, v0 = run(0)
    m1, v1 = run(pad)
    m2, v2 = run(2 * pad)
    assert abs(m1 - m2) < 0.02 and abs(v1 - v2) < 0.02
    assert v0 > 1.3 * v2  # without padding the edge variance is too large (measured 0.176 against 0.112)
