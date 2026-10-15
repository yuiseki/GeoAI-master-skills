"""uvx --with numpy --with pandas --with statsmodels --with pytest pytest test_estimate_effect_crosscheck.py

estimate_effect against statsmodels' TreatmentEffect (ra, ipw with normalised weights, aipw), on synthetic data
and, with GEOAI_REALDATA=1, on the National Supported Work data of Dehejia and Wahba (network access to
users.nber.org): the randomised experiment, and its treated men against survey controls (PSID, CPS).
"""

import os

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from statsmodels.treatment.treatment_effects import TreatmentEffect

from estimate_effect import effects, fit_logit


def _statsmodels(y, t, x, z):
    sel = sm.Logit(t, sm.add_constant(z)).fit(disp=0, method="newton", tol=1e-12, maxiter=200)
    te = TreatmentEffect(sm.OLS(y, sm.add_constant(x)), t.astype(int), results_select=sel)
    out = {}
    for target, group in (("ate", "all"), ("att", 1)):
        out[target] = {"ra": te.ra(return_results=False, effect_group=group)[0],
                       "ipw": te.ipw(return_results=False, effect_group=group)[0]}
    out["ate"]["aipw"] = te.aipw(return_results=False)[0]
    return out, sel.predict()


def _check(y, t, x, z, rel=1e-6):
    ref, p_ref = _statsmodels(y, t, x, z)
    assert fit_logit(z, t)["p"] == pytest.approx(p_ref, rel=1e-6, abs=1e-12)
    ours = {target: effects(y, t, x, z, target) for target in ("ate", "att")}
    for target, d in ref.items():
        for m, v in d.items():
            assert ours[target][m] == pytest.approx(v, rel=rel), (target, m)
    return ours


@pytest.mark.parametrize("seed", range(5))
def test_synthetic_against_statsmodels(seed):
    r = np.random.default_rng(seed)
    n = 800
    x = r.normal(size=(n, 3))
    t = (r.random(n) < 1 / (1 + np.exp(-(x @ [0.6, -0.4, 0.3] + 0.2 * x[:, 0] ** 2)))).astype(float)
    y = 1.5 * t + x @ [1.0, 0.5, -0.7] + 0.8 * t * x[:, 1] + r.normal(size=n)
    _check(y, t, x, x)
    _check(y, t, x[:, :2], np.c_[x, x[:, 0] ** 2])


NSW = "https://users.nber.org/~rdehejia/data/{}.dta"


def _nsw(controls):
    d = pd.read_stata(NSW.format("nsw_dw"))
    if controls != "experiment":
        d = pd.concat([d[d.treat == 1], pd.read_stata(NSW.format(controls))], ignore_index=True)
    d = d.drop(columns="data_id").astype(float)
    d["age2"], d["educ2"] = d.age ** 2, d.education ** 2
    d["u74"], d["u75"] = (d.re74 == 0).astype(float), (d.re75 == 0).astype(float)
    cov = ["age", "age2", "education", "educ2", "black", "hispanic", "married", "nodegree", "re74", "re75", "u74",
           "u75"]
    return d.re78.to_numpy(), d.treat.to_numpy(), d[cov].to_numpy(), d


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
@pytest.mark.parametrize("controls, rows, treated", [("experiment", 445, 185), ("psid_controls", 2675, 185),
                                                     ("cps_controls", 16177, 185)])
def test_nsw_against_statsmodels(controls, rows, treated):
    y, t, x, _ = _nsw(controls)
    assert (len(y), int(t.sum())) == (rows, treated)
    ours = _check(y, t, x, x, rel=1e-5)
    if controls == "experiment":  # randomised: the difference of means is the benchmark, 1794.3
        assert ours["att"]["naive"] == pytest.approx(1794.34, abs=0.01)
