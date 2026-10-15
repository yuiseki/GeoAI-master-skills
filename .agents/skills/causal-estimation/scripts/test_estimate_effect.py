"""uvx --with numpy --with pytest pytest test_estimate_effect.py"""

import numpy as np
import pytest

from estimate_effect import balance, bootstrap, diagnostics, effects, fit_logit, trim


def _two_strata():
    # stratum A (x = 0): treated 3, 5; untreated 1. Stratum B (x = 1): treated 12; untreated 6, 8, 7.
    y = np.array([3, 5, 1, 12, 6, 8, 7], float)
    t = np.array([1, 1, 0, 1, 0, 0, 0])
    x = np.array([0, 0, 0, 1, 1, 1, 1], float)[:, None]
    return y, t, x


def test_saturated_strata_give_the_standardised_effect_for_every_estimator():
    # differences 3 (A) and 12 - 7 = 5 (B). ATE weights by all rows 3 : 4, ATT by the treated 2 : 1.
    y, t, x = _two_strata()
    ate = effects(y, t, x, target="ate")
    att = effects(y, t, x, target="att")
    for m in ("ra", "ipw", "aipw"):
        assert ate[m] == pytest.approx(29 / 7, abs=1e-8)
        assert att[m] == pytest.approx(11 / 3, abs=1e-8)
    assert ate["naive"] == pytest.approx(20 / 3 - 22 / 4)


def test_logit_reaches_the_stratum_shares():
    y, t, x = _two_strata()
    p = fit_logit(x, t)["p"]
    assert p[:3] == pytest.approx([2 / 3] * 3, abs=1e-9)
    assert p[3:] == pytest.approx([1 / 4] * 4, abs=1e-9)


def test_complete_separation_stops():
    x = np.array([0, 1, 2, 3, 4, 5], float)[:, None]
    t = np.array([0, 0, 0, 1, 1, 1])
    with pytest.raises(ValueError, match="separat"):
        fit_logit(x, t)


def _world(seed, n=20000, ps="x", outcome="x"):
    """Effect 2. The treatment depends on x (ps="x") or on x squared; the outcome on x or x squared."""
    r = np.random.default_rng(seed)
    x = r.uniform(-2, 2, n)
    z = 0.8 * x if ps == "x" else 1.2 * (x ** 2 - 4 / 3)
    t = (r.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    f = 3 * x if outcome == "x" else 3 * x ** 2
    y = 1 + 2 * t + f + r.normal(0, 1, n)
    return y, t, x


def _cols(x, which):
    return (x if which == "x" else x ** 2)[:, None]


def test_all_three_recover_the_effect_when_both_models_are_right():
    y, t, x = _world(1, ps="x2", outcome="x2")
    e = effects(y, t, _cols(x, "x2"), x_ps=_cols(x, "x2"))
    for m in ("ra", "ipw", "aipw"):
        assert e[m] == pytest.approx(2, abs=0.1)
    assert abs(e["naive"] - 2) > 0.5


def test_wrong_outcome_model_breaks_ra_only():
    y, t, x = _world(2, ps="x2", outcome="x2")
    e = effects(y, t, _cols(x, "x"), x_ps=_cols(x, "x2"))
    assert abs(e["ra"] - 2) > 0.5
    assert e["ipw"] == pytest.approx(2, abs=0.15)
    assert e["aipw"] == pytest.approx(2, abs=0.15)


def test_wrong_propensity_model_breaks_ipw_only():
    y, t, x = _world(3, ps="x2", outcome="x2")
    e = effects(y, t, _cols(x, "x2"), x_ps=_cols(x, "x"))
    assert abs(e["ipw"] - 2) > 0.5
    assert e["ra"] == pytest.approx(2, abs=0.1)
    assert e["aipw"] == pytest.approx(2, abs=0.1)


def test_both_wrong_breaks_aipw_too():
    y, t, x = _world(4, ps="x2", outcome="x2")
    e = effects(y, t, _cols(x, "x"), x_ps=_cols(x, "x"))
    for m in ("ra", "ipw", "aipw"):
        assert abs(e[m] - 2) > 0.5


def test_an_unmeasured_confounder_biases_every_estimator_alike():
    r = np.random.default_rng(5)
    n = 20000
    x = r.normal(size=n)
    u = (r.random(n) < 0.5).astype(float)  # adds 3 to y and raises the chance of treatment
    t = (r.random(n) < 1 / (1 + np.exp(-(0.5 * x + 1.5 * u - 0.75)))).astype(int)
    y = 2 * t + x + 3 * u + r.normal(size=n)
    e = effects(y, t, x[:, None])
    bias = 3 * (u[t == 1].mean() - u[t == 0].mean())  # roughly: gamma x the difference in prevalence
    for m in ("ra", "ipw", "aipw"):
        assert e[m] - 2 == pytest.approx(bias, abs=0.25)
        assert e[m] - 2 > 1


def test_att_differs_from_ate_when_the_effect_varies():
    r = np.random.default_rng(6)
    n = 20000
    x = r.uniform(0, 2, n)
    t = (r.random(n) < 1 / (1 + np.exp(-(2 * x - 2)))).astype(int)
    y = (1 + 2 * x) * t + x + r.normal(size=n)  # effect 1 + 2x: the treated have larger x
    xx = x[:, None]
    ate, att = effects(y, t, xx, target="ate"), effects(y, t, xx, target="att")
    true_att = (1 + 2 * x[t == 1]).mean()
    assert ate["aipw"] == pytest.approx(3, abs=0.1)
    assert att["aipw"] == pytest.approx(true_att, abs=0.1)
    assert att["ra"] == pytest.approx(true_att, abs=0.1)
    assert att["ipw"] == pytest.approx(true_att, abs=0.1)
    assert true_att - 3 > 0.3


def test_weights_balance_the_covariate_when_the_propensity_is_right():
    y, t, x = _world(7, ps="x", outcome="x")
    p = fit_logit(x[:, None], t)["p"]
    b = balance(x[:, None], t, p, ["x"], target="ate")[0]
    assert abs(b["smd_before"]) > 0.5
    assert abs(b["smd_after"]) < 0.02


def test_poor_overlap_shows_in_the_diagnostics():
    r = np.random.default_rng(8)
    n = 4000
    x = r.normal(size=n)
    good = (r.random(n) < 1 / (1 + np.exp(-0.5 * x))).astype(int)
    poor = (r.random(n) < 1 / (1 + np.exp(-4 * x))).astype(int)
    dg = diagnostics(good, fit_logit(x[:, None], good)["p"])
    dp = diagnostics(poor, fit_logit(x[:, None], poor)["p"])
    assert dg["outside"] == 0
    assert dp["outside"] > 0.3
    assert dp["ess"][0] < 0.3 * dp["n"][0]
    assert dg["ess"][0] > 0.8 * dg["n"][0]


def test_trimming_reports_who_left():
    r = np.random.default_rng(9)
    n = 4000
    x = r.normal(size=n)
    t = (r.random(n) < 1 / (1 + np.exp(-4 * x))).astype(int)
    keep = trim(fit_logit(x[:, None], t)["p"], 0.05)
    assert 0 < keep.sum() < n
    assert keep.sum() == pytest.approx(n * (1 - diagnostics(t, fit_logit(x[:, None], t)["p"])["outside"]))


def test_cluster_bootstrap_widens_the_interval_for_clustered_treatment():
    # 40 regions; treatment and an outcome shock are shared within a region.
    r = np.random.default_rng(10)
    g = np.repeat(np.arange(40), 50)
    x = r.normal(size=g.size)
    t = (r.random(40) < 0.5).astype(int)[g]
    y = 2 * t + x + r.normal(0, 2, 40)[g] + r.normal(size=g.size)
    xx = x[:, None]
    iid = bootstrap(y, t, xx, n_boot=200, seed=0)
    clu = bootstrap(y, t, xx, n_boot=200, seed=0, cluster=g)
    assert clu["aipw"]["se"] > 3 * iid["aipw"]["se"]
    assert clu["failed"] == 0


def test_bootstrap_counts_draws_that_fail():
    # nearly separated: some resamples separate completely and are counted, not hidden.
    x = np.array([0, 1, 2, 3, 4, 5, 6, 7], float)[:, None]
    t = np.array([0, 0, 0, 1, 0, 1, 1, 1])
    y = np.arange(8, dtype=float)
    b = bootstrap(y, t, x, n_boot=200, seed=0)
    assert b["failed"] > 0
    assert b["failed"] + b["used"] == 200


def test_normalised_ipw_does_not_move_when_a_constant_is_added_to_the_outcome():
    # Hajek weights sum to one in each arm; unnormalised (Horvitz-Thompson) weights do not, so a shift of the
    # outcome by 1000 moves that estimate by 1000 x (sum t/p / n - sum (1-t)/(1-p) / n).
    y, t, x = _world(11, n=3000, ps="x", outcome="x")
    for target in ("ate", "att"):
        a = effects(y, t, x[:, None], target=target)
        b = effects(y + 1000, t, x[:, None], target=target)
        for m in ("ra", "ipw", "aipw"):
            assert b[m] == pytest.approx(a[m], abs=1e-6)
