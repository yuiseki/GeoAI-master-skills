"""uvx --from 'duckdb>=1.5.5' --with numpy --with statsmodels --with pytest pytest test_gibbs_crosscheck.py

No Python package fits Strauss models (spatstat, the reference implementation, is R; R is not installed here).
Two checks with statsmodels' GLM instead:
- the same Berman-Turner quadrature, fitted as a Poisson GLM of 1 / weight with var_weights = weight: checks
  this script's Newton iterations;
- the logistic-regression form of the pseudo-likelihood (Baddeley, Coeurjolly, Rubak and Waagepetersen 2014):
  data points against independent random dummy points of known intensity rho, a binomial GLM with offset
  -log rho. A different approximation of the same estimator: it agrees as the dummies grow, not exactly.
"""

import numpy as np
import pytest

from gibbs import _quadrature, fit, neighbours_within, simulate

sm = pytest.importorskip("statsmodels.api")
W = (0.0, 1.0, 0.0, 1.0)


def test_newton_matches_a_weighted_poisson_glm_on_the_same_quadrature():
    x, y = simulate(150, 0.3, 0.05, W, seed=2)
    ours = fit(x, y, W, 0.05)
    ux, uy, w, is_data, t = _quadrature(x, y, W, 0.05, 60)
    z = is_data / w
    g = sm.GLM(z, np.c_[np.ones(len(t)), t], family=sm.families.Poisson(), var_weights=w).fit(tol=1e-12)
    assert np.exp(g.params[0]) == pytest.approx(ours["beta"], rel=1e-8)
    assert np.exp(g.params[1]) == pytest.approx(ours["gamma"], rel=1e-8)


def test_logistic_regression_with_random_dummies_agrees_with_the_quadrature():
    diffs = []
    for s in range(5):
        x, y = simulate(150, 0.3, 0.05, W, seed=10 + s)
        ours = fit(x, y, W, 0.05, grid=80)
        r = 0.05
        e = (W[0] + r, W[1] - r, W[2] + r, W[3] - r)
        rng = np.random.default_rng(s)
        rho = 8000.0
        m = rng.poisson(rho * (e[1] - e[0]) * (e[3] - e[2]))
        dx, dy = rng.uniform(e[0], e[1], m), rng.uniform(e[2], e[3], m)
        inside = (x >= e[0]) & (x <= e[1]) & (y >= e[2]) & (y <= e[3])
        t_data = neighbours_within(x[inside], y[inside], x, y, r) - 1
        t_dummy = neighbours_within(dx, dy, x, y, r)
        t = np.r_[t_data, t_dummy]
        resp = np.r_[np.ones(inside.sum()), np.zeros(m)]
        g = sm.GLM(resp, np.c_[np.ones(len(t)), t], family=sm.families.Binomial(),
                   offset=np.full(len(t), -np.log(rho))).fit(tol=1e-12)
        diffs.append((np.exp(g.params[1]) - ours["gamma"], np.exp(g.params[0]) / ours["beta"] - 1))
    d = np.array(diffs)
    assert np.abs(d[:, 0]).max() < 0.06  # gamma
    assert np.abs(d[:, 1]).max() < 0.06  # beta, relative
