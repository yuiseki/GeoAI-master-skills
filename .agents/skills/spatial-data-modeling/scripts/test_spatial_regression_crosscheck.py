"""uvx --with numpy --with scipy --with spreg --with libpysal --with pytest pytest test_spatial_regression_crosscheck.py

spatial_regression against spreg 1.9.1 (ML_Lag and ML_Error with method="full", OLS with spat_diag) on the
Columbus neighbourhood crime data bundled with libpysal 4.15 (49 units, Queen contiguity, row-standardised):
CRIME on INC and HOVAL.
"""

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import libpysal  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
import spreg  # noqa: E402

from spatial_regression import impacts, lm_tests, ml_error, ml_lag  # noqa: E402


@pytest.fixture(scope="module")
def columbus():
    db = libpysal.io.open(libpysal.examples.get_path("columbus.dbf"))
    y = np.array(db.by_col("CRIME"), float).reshape(-1, 1)
    x = np.c_[db.by_col("INC"), db.by_col("HOVAL")].astype(float)
    w = libpysal.weights.Queen.from_shapefile(libpysal.examples.get_path("columbus.shp"))
    w.transform = "r"
    W = w.full()[0]
    return y, x, w, W


def test_lm_tests_match_spreg(columbus):
    y, x, w, W = columbus
    ref = spreg.OLS(y, x, w=w, spat_diag=True)
    ours = lm_tests(y.ravel(), np.c_[np.ones(len(y)), x], W)
    for k in ("lm_lag", "lm_error", "rlm_lag", "rlm_error"):
        assert ours[k][0] == pytest.approx(getattr(ref, k)[0], rel=1e-8), k


def test_ml_lag_matches_spreg(columbus):
    y, x, w, W = columbus
    ref = spreg.ML_Lag(y, x, w=w, method="full")
    ours = ml_lag(y.ravel(), np.c_[np.ones(len(y)), x], W)
    assert ours["rho"] == pytest.approx(ref.rho, rel=1e-5)
    assert ours["beta"] == pytest.approx(ref.betas[:3].ravel(), rel=1e-5)
    assert ours["loglik"] == pytest.approx(ref.logll, rel=1e-8)
    assert np.r_[ours["se_beta"], ours["se_rho"]] == pytest.approx(ref.std_err, rel=1e-3)
    imp = impacts(ours["rho"], ours["beta"][1:], W)
    assert imp["total"][0] == pytest.approx(ours["beta"][1] / (1 - ours["rho"]))


def test_ml_error_matches_spreg(columbus):
    y, x, w, W = columbus
    ref = spreg.ML_Error(y, x, w=w, method="full")
    ours = ml_error(y.ravel(), np.c_[np.ones(len(y)), x], W)
    assert ours["lambda"] == pytest.approx(ref.lam, rel=1e-5)
    assert ours["beta"] == pytest.approx(ref.betas[:3].ravel(), rel=1e-5)
    assert ours["loglik"] == pytest.approx(ref.logll, rel=1e-8)
    assert np.r_[ours["se_beta"], ours["se_lambda"]] == pytest.approx(ref.std_err, rel=1e-3)
