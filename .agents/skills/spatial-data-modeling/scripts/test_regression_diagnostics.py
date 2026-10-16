"""uvx --with numpy --with scipy --with duckdb --with pytest pytest test_regression_diagnostics.py"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from regression_diagnostics import breusch_pagan, condition_numbers, diagnose, jarque_bera, ols, white


def _design(n, rng, k=2):
    return np.c_[np.ones(n), rng.normal(size=(n, k))]


def test_ols_recovers_known_coefficients_and_hc3_by_hand():
    X = np.c_[np.ones(4), [0.0, 1, 2, 3]]
    y = np.array([1.0, 3, 5, 8])
    r = ols(X, y)
    beta = np.linalg.solve(X.T @ X, X.T @ y)
    assert r["beta"] == pytest.approx(beta)
    e = y - X @ beta
    h = np.einsum("ij,jk,ik->i", X, np.linalg.inv(X.T @ X), X)
    meat = X.T @ (X * (e / (1 - h))[:, None] ** 2)
    bread = np.linalg.inv(X.T @ X)
    assert r["se_hc3"] == pytest.approx(np.sqrt(np.diag(bread @ meat @ bread)))


def test_breusch_pagan_is_n_times_r2_of_squared_residuals():
    rng = np.random.default_rng(0)
    X = _design(200, rng)
    e = rng.normal(size=200)
    u = e ** 2
    fit = np.linalg.lstsq(X, u, rcond=None)[0]
    r2 = 1 - ((u - X @ fit) ** 2).sum() / ((u - u.mean()) ** 2).sum()
    lm, p = breusch_pagan(e, X)
    assert lm == pytest.approx(200 * r2) and 0 < p < 1


def test_jarque_bera_by_hand():
    e = np.array([-2.0, -1, 0, 0, 1, 5])
    z = e - e.mean()
    s = (z ** 3).mean() / (z ** 2).mean() ** 1.5
    k = (z ** 4).mean() / (z ** 2).mean() ** 2
    assert jarque_bera(e)[0] == pytest.approx(6 / 6 * (s ** 2 + (k - 3) ** 2 / 4))


def test_heteroskedasticity_breaks_plain_intervals_and_hc3_repairs_them():
    # Noise grows with |x|: the slope stays unbiased, but the plain standard error is too small. Breusch-
    # Pagan regresses the squared residuals on x itself and misses a spread that is symmetric in x; White's
    # test, with x squared, finds it.
    covered_plain, covered_hc3, rejected, rejected_white = 0, 0, 0, 0
    for seed in range(300):
        rng = np.random.default_rng(seed)
        x = rng.normal(size=200)
        y = 1 + 2 * x + rng.normal(size=200) * (0.2 + 1.5 * np.abs(x))
        r = ols(np.c_[np.ones(200), x], y)
        covered_plain += abs(r["beta"][1] - 2) <= 1.96 * r["se"][1]
        covered_hc3 += abs(r["beta"][1] - 2) <= 1.96 * r["se_hc3"][1]
        rejected += breusch_pagan(r["resid"], np.c_[np.ones(200), x])[1] <= 0.05
        rejected_white += white(r["resid"], np.c_[np.ones(200), x])[1] <= 0.05
    assert covered_plain / 300 < 0.85
    assert covered_hc3 / 300 > 0.92
    assert rejected / 300 < 0.5
    assert rejected_white / 300 > 0.95


def test_breusch_pagan_finds_a_spread_that_grows_linearly():
    rejected = 0
    for seed in range(100):
        rng = np.random.default_rng(seed)
        x = rng.uniform(0, 3, 200)
        y = 1 + 2 * x + rng.normal(size=200) * (0.2 + x)
        rejected += breusch_pagan(ols(np.c_[np.ones(200), x], y)["resid"], np.c_[np.ones(200), x])[1] <= 0.05
    assert rejected / 100 > 0.95


def test_non_normal_errors_reject_jarque_bera_but_intervals_still_cover_at_large_n():
    covered, rejected = 0, 0
    for seed in range(300):
        rng = np.random.default_rng(seed)
        x = rng.normal(size=1000)
        y = 1 + 2 * x + (rng.exponential(size=1000) - 1)  # skewed, homoskedastic
        r = ols(np.c_[np.ones(1000), x], y)
        covered += abs(r["beta"][1] - 2) <= 1.96 * r["se"][1]
        rejected += jarque_bera(r["resid"])[1] <= 0.05
    assert rejected / 300 > 0.99
    assert 0.92 < covered / 300 < 0.98


def test_condition_number_depends_on_units_unless_columns_are_scaled():
    rng = np.random.default_rng(3)
    X = _design(300, rng)
    big = X.copy()
    big[:, 1] *= 1000  # the same variable in other units
    raw, scaled = condition_numbers(X), condition_numbers(big)
    assert scaled["raw"] > 100 * raw["raw"]
    assert scaled["scaled"] == pytest.approx(raw["scaled"])


def test_collinearity_raises_the_scaled_condition_number_and_the_slope_spread():
    rng = np.random.default_rng(4)
    x1 = rng.normal(size=300)
    near = np.c_[np.ones(300), x1, x1 + rng.normal(scale=0.01, size=300)]
    far = np.c_[np.ones(300), x1, rng.normal(size=300)]
    assert condition_numbers(near)["scaled"] > 50 * condition_numbers(far)["scaled"]
    y = 1 + near[:, 1] + near[:, 2] + rng.normal(size=300)
    assert ols(near, y)["se"][1] > 30 * ols(far, 1 + far[:, 1] + far[:, 2] + rng.normal(size=300))["se"][1]


def test_rank_deficient_design_stops():
    X = np.c_[np.ones(10), np.arange(10.0), 2 * np.arange(10.0)]
    with pytest.raises(SystemExit, match="rank"):
        diagnose(X, np.arange(10.0), ["const", "a", "b"])


def test_cli_prints_every_diagnostic_and_counts_rows(tmp_path):
    rng = np.random.default_rng(5)
    x = rng.normal(size=50)
    rows = "\n".join(f"{i},{x[i]},{1 + 2 * x[i] + rng.normal()}" for i in range(50))
    (tmp_path / "t.csv").write_text("id,x,y\n" + rows + "\n")
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("regression_diagnostics.py")),
                          str(tmp_path / "t.csv"), "y", "x"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    for word in ("rows 50", "Breusch-Pagan", "White", "Jarque-Bera", "condition number", "HC3"):
        assert word in out.stdout
