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


def test_local_collinearity_by_hand_on_orthogonal_and_correlated_columns():
    from gwr import local_collinearity

    # An unbounded Gaussian kernel: every unit sees all rows with equal weight, so the local diagnostics are the
    # global ones. Columns 1, x, z with x and z orthogonal and centred: condition number 1, VIF 1.
    coords = _grid(4)
    x = np.array([1.0, -1, 1, -1] * 4)
    z = np.repeat([1.0, -1, 1, -1], 4)
    lc = local_collinearity(coords, np.c_[np.ones(16), x, z], 1e9, "gaussian", fixed=True)
    assert lc["condition"] == pytest.approx(np.ones(16), abs=1e-6)
    assert lc["vif"] == pytest.approx(np.ones((16, 2)), abs=1e-6)
    # Correlated pair with correlation r: VIF = 1 / (1 - r^2)
    rng = np.random.default_rng(0)
    a = rng.normal(size=16)
    b = 0.8 * a + 0.6 * rng.normal(size=16)
    lc = local_collinearity(coords, np.c_[np.ones(16), a, b], 1e9, "gaussian", fixed=True)
    r = np.corrcoef(a, b)[0, 1]
    assert lc["correlation"][:, 0] == pytest.approx(np.full(16, r), abs=1e-6)
    assert lc["vif"][:, 0] == pytest.approx(np.full(16, 1 / (1 - r * r)), rel=1e-6)
    assert ((lc["vdp"] >= 0) & (lc["vdp"] <= 1)).all()


def test_collinearity_in_one_region_shows_in_the_local_condition_number_and_the_slopes_there():
    # Both slopes are 1 everywhere. In the western third, x2 is x1 plus a little noise; elsewhere independent.
    # The local condition number is large only in the west, and only there do the local slopes swing.
    from gwr import local_collinearity

    coords = _grid(15)
    rng = np.random.default_rng(7)
    x1 = rng.normal(size=225)
    west = coords[:, 0] < 5
    x2 = np.where(west, x1 + 0.05 * rng.normal(size=225), rng.normal(size=225))
    X = np.c_[np.ones(225), x1, x2]
    y = 1 + x1 + x2 + 0.5 * rng.normal(size=225)
    lc = local_collinearity(coords, X, 25)
    r = gwr(coords, y, X, 25)
    deep_west, east = coords[:, 0] <= 1, coords[:, 0] >= 10
    assert np.median(lc["condition"][deep_west]) > 10 * np.median(lc["condition"][east])
    assert np.median(lc["condition"][deep_west]) > 30
    assert r["params"][deep_west, 1].std() > 3 * r["params"][east, 1].std()
    assert (lc["vdp"][deep_west][:, 1:] > 0.5).all()  # both slopes share the smallest singular value there
