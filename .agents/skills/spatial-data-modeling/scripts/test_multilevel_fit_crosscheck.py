"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with statsmodels --with pytest pytest test_multilevel_fit_crosscheck.py

multilevel_fit (statsmodels MixedLM underneath) against an independent random-intercept REML written from the
formula and maximised with scipy. With V_g = sigma2 I + tau2 J for each group, the restricted log-likelihood is
-1/2 [sum_g log|V_g| + log|X' V^-1 X| + r' V^-1 r], r the GLS residuals; V_g^-1 and |V_g| have closed forms.
An unbalanced synthetic data set; set GEOAI_REALDATA=1 to also run WDI life expectancy with a random
intercept per country.
"""

import os

import numpy as np
import pytest
from scipy.optimize import minimize

from multilevel_fit import fit


def _reml(y, X, group):
    X = np.c_[np.ones(len(y)), X]
    labels, codes = np.unique(group, return_inverse=True)
    n = np.bincount(codes)
    SX = np.zeros((len(labels), X.shape[1]))
    np.add.at(SX, codes, X)
    SY = np.bincount(codes, y)
    XtX, Xty = X.T @ X, X.T @ y

    def parts(p):
        s2, t2 = np.exp(p)
        c = t2 / (s2 * (s2 + n * t2))  # V_g^-1 = I / s2 - c_g J
        A = XtX / s2 - (SX * c[:, None]).T @ SX
        beta = np.linalg.solve(A, Xty / s2 - (SX * (c * SY)[:, None]).sum(0))
        r = y - X @ beta
        sr = np.bincount(codes, r)
        logdet = ((n - 1) * np.log(s2) + np.log(s2 + n * t2)).sum()
        return beta, logdet + np.linalg.slogdet(A)[1] + r @ r / s2 - (c * sr ** 2).sum()

    start = minimize(lambda p: parts(p)[1], [0.0, 0.0], method="Nelder-Mead",
                     options={"xatol": 1e-10, "fatol": 1e-12, "maxiter": 20_000}).x
    best = minimize(lambda p: parts(p)[1], start, method="BFGS", options={"gtol": 1e-10}).x
    return {"beta": parts(best)[0], "sigma2": float(np.exp(best[0])), "tau2": float(np.exp(best[1]))}


def _compare(y, X, group, names):
    ours = fit(y, X, group, names=names)
    ref = _reml(y, X, group)
    assert ours["tau2"] == pytest.approx(ref["tau2"], rel=1e-5)
    assert ours["sigma2"] == pytest.approx(ref["sigma2"], rel=1e-5)
    assert [ours["coef"][c] for c in ["const"] + names] == pytest.approx(ref["beta"], rel=1e-5, abs=1e-8)


def test_random_intercept_reml_matches_an_independent_implementation():
    rng = np.random.default_rng(0)
    n = rng.choice([1, 2, 5, 20], 80)
    group = np.repeat(np.arange(80), n)
    x = rng.normal(0, 1, (len(group), 2))
    y = 1 + x @ [0.5, -0.3] + rng.normal(0, 0.8, 80)[group] + rng.normal(0, 1, len(group))
    _compare(y, x, group, ["x1", "x2"])


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_wdi_life_expectancy_with_a_random_intercept_per_country():
    duckdb = pytest.importorskip("duckdb")
    w = "hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/"
    rows = duckdb.sql(f"""
        select k."Country Code",
          max(value) filter (where indicator_code = 'SP.DYN.LE00.IN') as le,
          ln(max(value) filter (where indicator_code = 'NY.GDP.PCAP.KD')) as lgdp,
          max(value) filter (where indicator_code = 'SP.URB.TOTL.IN.ZS') as urban
        from '{w}data.parquet' d join '{w}countries.parquet' k on d.country_code = k."Country Code"
        where k."Region" <> '' and d.year between 2000 and 2019
          and indicator_code in ('SP.DYN.LE00.IN', 'NY.GDP.PCAP.KD', 'SP.URB.TOTL.IN.ZS')
        group by k."Country Code", d.year""").fetchall()
    rows = [r for r in rows if None not in r]
    group = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows], float)
    X = np.array([r[2:] for r in rows], float)
    _compare(y, X, group, ["lgdp", "urban"])
