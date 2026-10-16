"""uvx --with numpy --with scipy --with pandas --with mgwr --with libpysal --with pytest pytest test_gwr_crosscheck.py

gwr against mgwr 2.2.1 on the Georgia county data bundled with libpysal 4.15 (159 counties, UTM metres):
PctBach on PctFB, PctBlack, PctRural (standardised), as in mgwr's examples. At the same bandwidth: local
coefficients, standard errors, tr(S), AICc, the adjusted critical t. The selected bandwidth: ours reaches an
AICc no worse than mgwr's golden-section search.
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

from gwr import aicc, gwr, select_bandwidth  # noqa: E402


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
