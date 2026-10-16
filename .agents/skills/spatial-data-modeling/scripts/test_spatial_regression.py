"""uvx --with numpy --with scipy --with pytest pytest test_spatial_regression.py

Many small dense solves: BLAS threads only fight over them (60 s against 2 s on the author's machine), so the
tests use one thread.
"""

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from spatial_regression import impacts, lm_tests, ml_error, ml_lag, rook_weights  # noqa: E402


def _grid_world(seed, side=15, rho=0.0, lam=0.0, beta=(1.0, 2.0)):
    W = rook_weights(side)
    n = side * side
    rng = np.random.default_rng(seed)
    X = np.c_[np.ones(n), rng.normal(size=n)]
    I = np.eye(n)
    eps = rng.normal(size=n)
    u = np.linalg.solve(I - lam * W, eps)
    y = np.linalg.solve(I - rho * W, X @ np.array(beta) + u)
    return y, X, W


def test_rook_weights_are_row_standardised_with_corner_and_edge_degrees():
    W = rook_weights(3)
    assert W.sum(1) == pytest.approx(np.ones(9))
    assert (W[0] > 0).sum() == 2 and (W[4] > 0).sum() == 4 and (W[1] > 0).sum() == 3


def test_ml_lag_recovers_rho_and_beta():
    rhos, b1 = [], []
    for seed in range(10):
        y, X, W = _grid_world(seed, rho=0.5)
        r = ml_lag(y, X, W)
        rhos.append(r["rho"])
        b1.append(r["beta"][1])
    assert np.mean(rhos) == pytest.approx(0.5, abs=0.05)
    assert np.mean(b1) == pytest.approx(2.0, abs=0.05)


def test_ml_error_recovers_lambda_and_beta():
    lams = []
    for seed in range(10):
        y, X, W = _grid_world(seed, lam=0.6)
        r = ml_error(y, X, W)
        lams.append(r["lambda"])
        assert r["beta"][1] == pytest.approx(2.0, abs=0.15)
    assert np.mean(lams) == pytest.approx(0.6, abs=0.06)


def test_ols_slope_under_a_lag_process_is_the_direct_impact_not_beta():
    # With x unrelated to location, OLS finds the own effect including feedback from the neighbours (the direct
    # impact), not beta, and says nothing of the spillover to the neighbours (the indirect impact).
    ols, direct = [], []
    for seed in range(10):
        y, X, W = _grid_world(seed, rho=0.6)
        ols.append(np.linalg.lstsq(X, y, rcond=None)[0][1])
        direct.append(impacts(0.6, [2.0], W)["direct"][0])
    assert np.mean(ols) == pytest.approx(np.mean(direct), abs=0.08)
    assert np.mean(ols) > 2.1


def test_lm_tests_point_to_the_process_that_made_the_data():
    y, X, W = _grid_world(1, lam=0.6)
    t = lm_tests(y, X, W)
    assert t["lm_error"][1] < 0.001 and t["rlm_error"][1] < 0.001
    assert t["rlm_lag"][1] > 0.01
    y, X, W = _grid_world(2, rho=0.5, beta=(1.0, 2.0))
    t = lm_tests(y, X, W)
    assert t["lm_lag"][1] < 0.001 and t["rlm_lag"][1] < 0.001


def test_no_dependence_gives_rho_near_zero_and_ols_like_estimates():
    y, X, W = _grid_world(3)
    r = ml_lag(y, X, W)
    assert abs(r["rho"]) < 0.1
    assert r["beta"] == pytest.approx(np.linalg.lstsq(X, y, rcond=None)[0], abs=0.1)


def test_impacts_split_the_total_into_direct_and_spillover():
    y, X, W = _grid_world(4, rho=0.5)
    r = ml_lag(y, X, W)
    imp = impacts(r["rho"], r["beta"][1:], W)
    assert imp["total"][0] == pytest.approx(r["beta"][1] / (1 - r["rho"]))
    assert imp["direct"][0] > r["beta"][1]  # feedback through the neighbours comes back
    assert imp["indirect"][0] == pytest.approx(imp["total"][0] - imp["direct"][0])


def test_standard_errors_cover_rho():
    covered = 0
    for seed in range(60):
        y, X, W = _grid_world(100 + seed, side=15, rho=0.4)
        r = ml_lag(y, X, W)
        covered += abs(r["rho"] - 0.4) <= 1.96 * r["se_rho"]
    assert covered / 60 >= 0.85
