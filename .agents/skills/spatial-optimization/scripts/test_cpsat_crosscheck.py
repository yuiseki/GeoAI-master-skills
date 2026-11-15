"""uvx --with numpy --with scipy --with ortools --with pytest pytest test_cpsat_crosscheck.py

Compare OR-Tools CP-SAT capacitated single-source facility location against an independent
MILP formulation solved with scipy.optimize.milp (HiGHS).
"""

import numpy as np
import pytest
from scipy.optimize import Bounds, LinearConstraint, milp

from cpsat_location import solve_cflp


def _cflp_scipy_milp(d, w, s, p, fc):
    n, m = d.shape
    # Variables: [x_00..x_{n-1,m-1} (n*m), y_0..y_{m-1} (m)]
    num_vars = n * m + m
    c = np.zeros(num_vars)
    for i in range(n):
        for j in range(m):
            c[i * m + j] = w[i] * d[i, j]
    for j in range(m):
        c[n * m + j] = fc[j]

    rows, lb, ub = [], [], []

    # 1. sum_j x_ij == 1
    for i in range(n):
        r = np.zeros(num_vars)
        r[i * m : (i + 1) * m] = 1.0
        rows.append(r)
        lb.append(1.0)
        ub.append(1.0)

    # 2. sum_i w_i x_ij - s_j y_j <= 0
    for j in range(m):
        r = np.zeros(num_vars)
        for i in range(n):
            r[i * m + j] = w[i]
        r[n * m + j] = -s[j]
        rows.append(r)
        lb.append(-np.inf)
        ub.append(0.0)

    # 3. x_ij - y_j <= 0
    for i in range(n):
        for j in range(m):
            r = np.zeros(num_vars)
            r[i * m + j] = 1.0
            r[n * m + j] = -1.0
            rows.append(r)
            lb.append(-np.inf)
            ub.append(0.0)

    # 4. sum_j y_j <= p
    r = np.zeros(num_vars)
    r[n * m :] = 1.0
    rows.append(r)
    lb.append(-np.inf)
    ub.append(float(p))

    res = milp(
        c,
        integrality=np.ones(num_vars),
        bounds=Bounds(0, 1),
        constraints=LinearConstraint(np.vstack(rows), lb, ub),
    )
    assert res.status == 0
    return float(res.fun)


@pytest.mark.parametrize("seed", range(5))
def test_cpsat_cflp_matches_scipy_milp(seed):
    rng = np.random.default_rng(seed + 10)
    n, m, p = 15, 6, 3
    dem_xy = rng.uniform(0, 20, (n, 2))
    fac_xy = rng.uniform(0, 20, (m, 2))
    d = np.round(np.linalg.norm(dem_xy[:, None, :] - fac_xy[None, :, :], axis=2), 2)
    w = rng.integers(1, 10, size=n).astype(float)
    s = np.full(m, float(np.ceil(w.sum() * 0.6)))
    fc = rng.integers(10, 50, size=m).astype(float)

    milp_obj = _cflp_scipy_milp(d, w, s, p, fc)
    cpsat_res = solve_cflp(d, w, s, p, fixed_cost=fc, scale=100)
    assert cpsat_res["status"] == "optimal"
    assert cpsat_res["recomputed"] == pytest.approx(milp_obj, abs=1e-2)
