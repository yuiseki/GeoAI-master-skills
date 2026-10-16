"""uvx --with numpy --with scipy --with pytest pytest test_iv.py"""

import numpy as np
import pytest

from iv import anderson_rubin, tsls


def _w(n):
    return np.ones((n, 1))


def test_just_identified_without_controls_is_the_ratio_of_covariances():
    rng = np.random.default_rng(0)
    z = rng.normal(size=200)
    x = z + rng.normal(size=200)
    y = 2 * x + rng.normal(size=200)
    r = tsls(y, x, z, _w(200))
    assert r["beta"][0] == pytest.approx(np.cov(z, y)[0, 1] / np.cov(z, x)[0, 1])


def test_binary_instrument_and_treatment_give_the_wald_ratio():
    rng = np.random.default_rng(1)
    z = rng.integers(0, 2, 400).astype(float)
    x = (rng.random(400) < 0.2 + 0.5 * z).astype(float)
    y = 3 * x + rng.normal(size=400)
    wald = (y[z == 1].mean() - y[z == 0].mean()) / (x[z == 1].mean() - x[z == 0].mean())
    assert tsls(y, x, z, _w(400))["beta"][0] == pytest.approx(wald)


def _confounded(seed, n=2000, pi=1.0, direct=0.0, noise=1.0):
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    u = rng.normal(size=n)  # unmeasured confounder
    x = pi * z + u + noise * rng.normal(size=n)
    y = 1.0 * x + 2 * u + direct * z + noise * rng.normal(size=n)
    return y, x, z


def test_iv_removes_confounding_that_ols_does_not():
    y, x, z = _confounded(2)
    ols = np.linalg.lstsq(np.c_[np.ones(len(y)), x], y, rcond=None)[0][1]
    assert ols > 1.5
    assert tsls(y, x, z, _w(len(y)))["beta"][0] == pytest.approx(1.0, abs=0.1)


def test_a_direct_path_from_the_instrument_biases_iv():
    y, x, z = _confounded(3, direct=0.5)
    assert tsls(y, x, z, _w(len(y)))["beta"][0] > 1.3  # 1 + 0.5 / pi: the exclusion restriction cannot be tested


def test_weak_instruments_pull_toward_ols_and_break_wald_intervals_but_not_anderson_rubin():
    est, wald_cover, ar_cover, F = [], 0, 0, []
    for seed in range(300):
        # A very weak instrument and strong endogeneity (the confounder dominates both errors).
        y, x, z = _confounded(100 + seed, n=300, pi=0.04, noise=0.2)
        r = tsls(y, x, z, _w(300))
        est.append(r["beta"][0])
        F.append(r["first_stage_F"])
        wald_cover += abs(r["beta"][0] - 1) <= 1.96 * r["se"][0]
        ar_cover += anderson_rubin(y, x, z, _w(300)).contains(1.0)
    assert np.median(F) < 2
    assert np.median(est) > 1.7  # pulled toward OLS (about 2)
    assert wald_cover / 300 < 0.85
    assert 0.92 <= ar_cover / 300 <= 0.98


def test_anderson_rubin_with_a_strong_instrument_is_a_bounded_interval_around_the_estimate():
    y, x, z = _confounded(4, pi=1.0)
    ar = anderson_rubin(y, x, z, _w(len(y)))
    r = tsls(y, x, z, _w(len(y)))
    assert ar.kind == "interval" and ar.lo < r["beta"][0] < ar.hi
    assert ar.hi - ar.lo == pytest.approx(2 * 1.96 * r["se_homoskedastic"][0], rel=0.15)


def test_anderson_rubin_with_no_instrument_strength_is_unbounded():
    rng = np.random.default_rng(5)
    z = rng.normal(size=300)
    x = rng.normal(size=300)  # unrelated to z
    y = x + rng.normal(size=300)
    assert anderson_rubin(y, x, z, _w(300)).kind in ("whole line", "two rays")


def test_late_is_the_effect_on_compliers():
    # Always-takers gain 5, compliers gain 2, never-takers would gain 8: IV recovers 2, not the mean effect.
    rng = np.random.default_rng(6)
    n = 20000
    kind = rng.choice(["always", "complier", "never"], size=n, p=[0.2, 0.5, 0.3])
    z = rng.integers(0, 2, n).astype(float)
    x = ((kind == "always") | ((kind == "complier") & (z == 1))).astype(float)
    gain = np.select([kind == "always", kind == "complier"], [5.0, 2.0], 8.0)
    y = gain * x + rng.normal(size=n)
    assert tsls(y, x, z, _w(n))["beta"][0] == pytest.approx(2.0, abs=0.15)


def test_cluster_standard_errors_widen_when_the_instrument_is_set_by_cluster():
    rng = np.random.default_rng(7)
    g = np.repeat(np.arange(40), 50)
    z = rng.normal(size=40)[g]
    shock = rng.normal(size=40)[g]
    x = z + rng.normal(size=2000)
    y = x + shock + rng.normal(size=2000)
    r = tsls(y, x, z, _w(2000), cluster=g)
    assert r["se_cluster"][0] > 3 * r["se"][0]


def test_controls_are_partialled_out():
    rng = np.random.default_rng(8)
    n = 3000
    w = rng.normal(size=n)
    z = rng.normal(size=n) + w
    u = rng.normal(size=n)
    x = z + u + w
    y = x + 3 * w + 2 * u + rng.normal(size=n)
    assert tsls(y, x, z, np.c_[np.ones(n), w])["beta"][0] == pytest.approx(1.0, abs=0.1)
