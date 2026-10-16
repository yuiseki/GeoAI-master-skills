"""uvx --with numpy --with scipy --with duckdb --with statsmodels --with pytest pytest test_regression_diagnostics_crosscheck.py

regression_diagnostics against statsmodels: OLS coefficients and plain and HC3 standard errors,
het_breuschpagan (studentised), het_white, jarque_bera, and the condition number of the design.
"""

import numpy as np
import pytest
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan, het_white
from statsmodels.stats.stattools import jarque_bera as sm_jb

from regression_diagnostics import breusch_pagan, condition_numbers, jarque_bera, ols, white


@pytest.mark.parametrize("seed", range(5))
def test_against_statsmodels(seed):
    rng = np.random.default_rng(seed)
    n = 300
    X = np.c_[np.ones(n), rng.normal(size=(n, 3))]
    X[:, 3] = X[:, 1] * 0.5 + rng.normal(size=n)
    y = X @ [1.0, 2.0, -1.0, 0.5] + rng.normal(size=n) * (0.5 + np.abs(X[:, 2]))
    ref = sm.OLS(y, X).fit()
    ours = ols(X, y)
    assert ours["beta"] == pytest.approx(ref.params, rel=1e-10)
    assert ours["se"] == pytest.approx(ref.bse, rel=1e-10)
    assert ours["se_hc3"] == pytest.approx(ref.get_robustcov_results("HC3").bse, rel=1e-10)
    lm, p, _, _ = het_breuschpagan(ref.resid, X)
    assert breusch_pagan(ours["resid"], X) == pytest.approx((lm, p), rel=1e-9)
    lmw, pw, _, _ = het_white(ref.resid, X)
    assert white(ours["resid"], X) == pytest.approx((lmw, pw), rel=1e-9)
    jb, pj, sk, ku = sm_jb(ref.resid)
    assert jarque_bera(ours["resid"]) == pytest.approx((jb, pj, sk, ku), rel=1e-9)
    assert condition_numbers(X)["raw"] == pytest.approx(ref.condition_number, rel=1e-8)
