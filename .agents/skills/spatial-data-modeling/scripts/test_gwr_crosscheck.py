"""uvx --with numpy --with scipy --with pandas --with mgwr --with libpysal --with pytest pytest test_gwr_crosscheck.py

gwr against mgwr 2.2.1 on the Georgia county data bundled with libpysal 4.15 (159 counties, UTM metres):
PctBach on PctFB, PctBlack, PctRural (standardised), as in mgwr's examples. At the same bandwidth: local
coefficients, standard errors, tr(S), AICc, the adjusted critical t. The selected bandwidth: ours reaches an
AICc no worse than mgwr's golden-section search. Local collinearity against GWRResults.local_collinearity():
correlations, VIFs and variance-decomposition proportions; the condition number with root=False, since mgwr
weights the design's rows by w rather than sqrt(w) (Wheeler 2007 uses W^(1/2) X, our default).
"""

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import libpysal  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from mgwr.gwr import GWR  # noqa: E402
from mgwr.sel_bw import Sel_BW  # noqa: E402

from gwr import aicc, gwr, local_collinearity, select_bandwidth  # noqa: E402


@pytest.fixture(scope="module")
def georgia():
    d = pd.read_csv(libpysal.examples.get_path("GData_utm.csv"))
    y = d.PctBach.to_numpy().reshape(-1, 1)
    F = d[["PctFB", "PctBlack", "PctRural"]].to_numpy()
    F = (F - F.mean(0)) / F.std(0)
    coords = d[["X", "Y"]].to_numpy().astype(float)
    return coords, y, F


@pytest.mark.parametrize("bw,kernel", [(117, "bisquare"), (60, "bisquare"), (90, "gaussian")])
def test_fit_matches_mgwr(georgia, bw, kernel):
    coords, y, F = georgia
    ref = GWR(coords, y, F, bw, kernel=kernel, fixed=False).fit()
    ours = gwr(coords, y.ravel(), np.c_[np.ones(len(y)), F], bw, kernel=kernel)
    assert ours["params"] == pytest.approx(ref.params, rel=1e-8, abs=1e-10)
    assert ours["bse"] == pytest.approx(ref.bse, rel=1e-8)
    assert ours["tr_S"] == pytest.approx(ref.tr_S, rel=1e-10)
    assert aicc(ours) == pytest.approx(ref.aicc, rel=1e-10)
    assert ours["critical_t"] == pytest.approx(ref.critical_tval(), rel=1e-10)


def test_selected_bandwidth_is_no_worse_than_mgwr(georgia):
    coords, y, F = georgia
    ref_bw = Sel_BW(coords, y, F).search()
    sel = select_bandwidth(coords, y.ravel(), np.c_[np.ones(len(y)), F])
    ref_aicc = GWR(coords, y, F, ref_bw).fit().aicc
    assert sel["aicc"] <= ref_aicc + 1e-9
    print("mgwr bw", ref_bw, ref_aicc, "ours", sel["bw"], sel["aicc"])


@pytest.mark.parametrize("bw,kernel", [(117, "bisquare"), (60, "bisquare"), (90, "gaussian")])
def test_local_collinearity_matches_mgwr(georgia, bw, kernel):
    coords, y, F = georgia
    corr, vif, cn, vdp = GWR(coords, y, F, bw, kernel=kernel, fixed=False).fit().local_collinearity()
    X = np.c_[np.ones(len(y)), F]
    ours = local_collinearity(coords, X, bw, kernel, root=False)
    np.testing.assert_allclose(ours["correlation"], corr, rtol=1e-8, atol=1e-10)
    np.testing.assert_allclose(ours["vif"], vif, rtol=1e-8)
    np.testing.assert_allclose(ours["condition"], cn.ravel(), rtol=1e-8)
    np.testing.assert_allclose(ours["vdp"], vdp, rtol=1e-7, atol=1e-10)
    wheeler = local_collinearity(coords, X, bw, kernel)["condition"]
    assert not np.allclose(wheeler, cn.ravel(), rtol=1e-3)  # the two definitions really differ


@pytest.fixture(scope="module")
def georgia_standardised(georgia):
    coords, y, F = georgia
    return coords, (y - y.mean()) / y.std(), F


def test_mgwr_closed_form_matches_mgwr_at_its_bandwidths(georgia_standardised):
    from mgwr.gwr import MGWR

    from gwr import mgwr

    coords, y, F = georgia_standardised
    sel = Sel_BW(coords, y, F, multi=True)
    bws = sel.search()
    exact = MGWR(coords, y, F, sel).exact_fit()
    backfit = MGWR(coords, y, F, sel).fit()
    ours = mgwr(coords, y.ravel(), np.c_[np.ones(len(y)), F], bws)
    np.testing.assert_allclose(ours["params"], exact.params, atol=1e-10)
    np.testing.assert_allclose(ours["bse"], exact.bse, rtol=1e-8)
    np.testing.assert_allclose(ours["enp"], exact.ENP_j, rtol=1e-10)
    np.testing.assert_allclose(ours["params"], backfit.params, atol=1e-4)  # mgwr's backfitting, tolerance 1e-5
    np.testing.assert_allclose(ours["critical_t"], exact.critical_tval(), rtol=1e-8)
    np.testing.assert_allclose(ours["critical_t"], backfit.critical_tval(), rtol=1e-4)  # from backfitted ENPs
    assert aicc(ours) == pytest.approx(exact.aicc, rel=1e-10)


def test_mgwr_bandwidths_reach_an_aicc_no_worse_than_mgwr(georgia_standardised):
    from gwr import mgwr, mgwr_select

    coords, y, F = georgia_standardised
    X = np.c_[np.ones(len(y)), F]
    theirs = Sel_BW(coords, y, F, multi=True).search()
    ours = mgwr_select(coords, y.ravel(), X)
    # Measured: ours [92, 23, 94, 145] (AICc 296.1, tr(S) 24.5), mgwr [101, 101, 117, 157] (297.1, 11.5). The
    # foreign-born share's one-column AICc rises only from 275.1 at 22 to 278.4 at 114: mgwr's golden section
    # stops at 101, 2.9 above the minimum that the coarse profile here finds.
    assert aicc(mgwr(coords, y.ravel(), X, ours["bws"])) <= aicc(mgwr(coords, y.ravel(), X, list(theirs))) + 1e-6
