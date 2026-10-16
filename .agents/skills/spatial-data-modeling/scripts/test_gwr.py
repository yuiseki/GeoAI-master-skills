"""uvx --with numpy --with scipy --with pytest pytest test_gwr.py"""

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gwr import aicc, gwr, select_bandwidth  # noqa: E402


def _grid(side=15):
    r, c = np.divmod(np.arange(side * side), side)
    return np.c_[c, r].astype(float)


def test_an_unbounded_gaussian_kernel_gives_back_ols():
    rng = np.random.default_rng(0)
    coords = _grid(8)
    X = np.c_[np.ones(64), rng.normal(size=64)]
    y = X @ [1.0, 2.0] + rng.normal(size=64)
    r = gwr(coords, y, X, 1e9, kernel="gaussian", fixed=True)
    ols = np.linalg.lstsq(X, y, rcond=None)[0]
    assert r["params"] == pytest.approx(np.tile(ols, (64, 1)), rel=1e-6)
    assert r["tr_S"] == pytest.approx(2, rel=1e-6)


def _varying(seed, side=15):
    coords = _grid(side)
    rng = np.random.default_rng(seed)
    n = side * side
    X = np.c_[np.ones(n), rng.normal(size=n)]
    b1 = 1 + coords[:, 0] / (side - 1) * 2  # the slope rises from 1 in the west to 3 in the east
    y = 1 + b1 * X[:, 1] + 0.5 * rng.normal(size=n)
    return coords, y, X, b1


def test_a_slope_that_changes_west_to_east_is_recovered():
    coords, y, X, b1 = _varying(1)
    bw = select_bandwidth(coords, y, X)["bw"]
    r = gwr(coords, y, X, bw)
    assert np.corrcoef(r["params"][:, 1], b1)[0, 1] > 0.9
    assert bw < 0.5 * len(y)


def test_a_constant_slope_gets_a_wide_bandwidth():
    coords = _grid(15)
    rng = np.random.default_rng(2)
    X = np.c_[np.ones(225), rng.normal(size=225)]
    y = X @ [1.0, 2.0] + rng.normal(size=225)
    sel = select_bandwidth(coords, y, X)
    assert sel["bw"] > 0.4 * len(y)


def test_effective_parameters_lie_between_k_and_n_and_fall_as_the_bandwidth_widens():
    coords, y, X, _ = _varying(3)
    narrow, wide = gwr(coords, y, X, 20), gwr(coords, y, X, 150)
    assert 2 < wide["tr_S"] < narrow["tr_S"] < len(y)


def test_aicc_by_hand():
    coords, y, X, _ = _varying(4)
    r = gwr(coords, y, X, 60)
    n, k = len(y), r["tr_S"]
    rss = (r["resid"] ** 2).sum()
    llf = -n / 2 * (1 + np.log(2 * np.pi * rss / n))
    assert aicc(r) == pytest.approx(-2 * llf + 2 * n * (k + 1) / (n - k - 2))


def test_collinear_predictors_make_local_slopes_trade_off():
    # x1 and x2 are nearly the same and both slopes are constant (1 and 1). Locally, the fit cannot tell them
    # apart, and the two local slopes move in opposite directions: an artefact, not spatial variation.
    coords = _grid(15)
    rng = np.random.default_rng(5)
    x1 = rng.normal(size=225)
    x2 = x1 + 0.2 * rng.normal(size=225)
    X = np.c_[np.ones(225), x1, x2]
    y = 1 + x1 + x2 + rng.normal(size=225)
    r = gwr(coords, y, X, 30)
    assert np.corrcoef(r["params"][:, 1], r["params"][:, 2])[0, 1] < -0.7


def test_adjusted_critical_t_is_stricter_than_1_96():
    coords, y, X, _ = _varying(6)
    r = gwr(coords, y, X, 40)
    assert r["critical_t"] > 2.2
    assert (np.abs(r["tvalues"][:, 1]) > r["critical_t"]).sum() <= (np.abs(r["tvalues"][:, 1]) > 1.96).sum()
