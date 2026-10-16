"""uvx --with numpy --with scipy --with pandas --with linearmodels --with statsmodels --with wooldridge --with pytest pytest test_iv_crosscheck.py

tsls against linearmodels 7.0 IV2SLS (debiased): coefficients, homoskedastic, robust and clustered standard
errors, the first-stage partial F and partial R^2. The Anderson-Rubin set's end points against statsmodels: at
each end the F test of the instrument in the regression of y - b x on the instrument and controls sits at its
critical value. With GEOAI_REALDATA=1, Card's (1995) return to schooling with nearness to a four-year college
as the instrument (the wooldridge package's card data).
"""

import os

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from linearmodels.iv import IV2SLS
from scipy import stats

from iv import anderson_rubin, tsls


def _data(seed, n=800):
    rng = np.random.default_rng(seed)
    w = rng.normal(size=(n, 2))
    z = rng.normal(size=n) + 0.3 * w[:, 0]
    u = rng.normal(size=n)
    x = 0.6 * z + u + 0.5 * w[:, 1] + rng.normal(size=n)
    y = x + w @ [1.0, -0.5] + 2 * u + rng.normal(size=n) * (1 + 0.5 * np.abs(w[:, 0]))
    g = rng.integers(0, 40, n)
    return pd.DataFrame({"y": y, "x": x, "z": z, "w1": w[:, 0], "w2": w[:, 1], "g": g, "const": 1.0})


@pytest.mark.parametrize("seed", range(3))
def test_tsls_matches_linearmodels(seed):
    d = _data(seed)
    W = d[["const", "w1", "w2"]]
    ours = tsls(d.y, d.x, d.z, W.to_numpy(), cluster=d.g.to_numpy())
    model = IV2SLS(d.y, W, d[["x"]], d[["z"]])
    for cov, key in (("unadjusted", "se_homoskedastic"), ("robust", "se")):
        ref = model.fit(cov_type=cov, debiased=True)
        assert ours["beta"][0] == pytest.approx(ref.params["x"], rel=1e-10)
        assert ours[key][0] == pytest.approx(ref.std_errors["x"], rel=1e-8)
    ref = model.fit(cov_type="clustered", clusters=d.g, debiased=True)
    assert ours["se_cluster"][0] == pytest.approx(ref.std_errors["x"], rel=1e-8)
    # linearmodels' first-stage F divides the residual variance by n unless debiased; ours by n - columns.
    fs = model.fit(cov_type="unadjusted", debiased=True).first_stage.diagnostics.loc["x"]
    assert ours["partial_r2"] == pytest.approx(fs["partial.rsquared"], rel=1e-8)
    assert ours["first_stage_F"] == pytest.approx(fs["f.stat"], rel=1e-8)


@pytest.mark.parametrize("seed", range(3))
def test_anderson_rubin_ends_sit_at_the_critical_value(seed):
    d = _data(seed)
    W = d[["const", "w1", "w2"]].to_numpy()
    ar = anderson_rubin(d.y, d.x, d.z, W)
    assert ar.kind == "interval"
    crit = stats.f.ppf(0.95, 1, len(d) - W.shape[1] - 1)
    for b in (ar.lo, ar.hi):
        f = sm.OLS(d.y - b * d.x, np.c_[d.z, W]).fit()
        assert f.tvalues.iloc[0] ** 2 == pytest.approx(crit, rel=1e-6)


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_card_return_to_schooling():
    import wooldridge

    d = wooldridge.data("card")
    controls = ["exper", "expersq", "black", "smsa", "south", "smsa66"] + [f"reg66{i}" for i in range(2, 10)]
    d = d.dropna(subset=["lwage", "educ", "nearc4", *controls]).assign(const=1.0)
    assert len(d) == 3010
    W = d[["const", *controls]]
    ours = tsls(d.lwage, d.educ, d.nearc4, W.to_numpy())
    ref = IV2SLS(d.lwage, W, d[["educ"]], d[["nearc4"]]).fit(cov_type="unadjusted", debiased=True)
    assert ours["beta"][0] == pytest.approx(ref.params["educ"], rel=1e-10)
    assert ours["beta"][0] == pytest.approx(0.132, abs=0.001)  # Wooldridge, example 15.4
    print("2SLS", ours["beta"][0], ours["se"][0], ours["se_homoskedastic"][0], "F", ours["first_stage_F"],
          "AR", anderson_rubin(d.lwage, d.educ, d.nearc4, W.to_numpy()))
