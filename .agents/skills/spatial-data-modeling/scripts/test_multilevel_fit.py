"""uvx --with statsmodels --with pytest pytest test_multilevel_fit.py

The three groups of three are worked out by hand; the random ones check a property of one seeded draw.
"""

import numpy as np
import pytest

from multilevel_fit import fit, group_means, icc_anova, shrink

# means 2, 6, 3; grand mean 11/3. Within: MSW = 6 / 6 = 1. Between: 3 x 78/9 = 26 on 2 df, MSB = 13.
# tau2 = (13 - 1) / 3 = 4, sigma2 = 1, ICC = 0.8
Y = np.array([1, 2, 3, 5, 6, 7, 2, 3, 4.0])
G = np.repeat(["A", "B", "C"], 3)


def test_icc_from_the_anova_table():
    r = icc_anova(Y, G)
    assert (r["tau2"], r["sigma2"], r["icc"]) == pytest.approx((4, 1, 0.8))


def test_a_negative_between_variance_is_reported_as_zero_and_flagged():
    # equal group means: MSB = 0, so tau2 = -MSW / 3 < 0
    r = icc_anova(np.array([1, 2, 3, 2, 1, 3, 3, 2, 1.0]), G)
    assert r["tau2"] == 0 and r["icc"] == 0 and r["at_zero"]


def test_partial_pooling_moves_each_group_mean_towards_the_overall_mean_by_its_reliability():
    r = shrink(Y, G, tau2=4, sigma2=1)
    # weight = tau2 / (tau2 + sigma2 / n) = 4 / (4 + 1/3) = 12/13; A: 11/3 + 12/13 (2 - 11/3) = 83/39
    assert r["weight"] == pytest.approx([12 / 13] * 3)
    assert r["pooled"][0] == pytest.approx(83 / 39)


def test_a_group_with_one_row_is_pulled_harder():
    y = np.array([1, 2, 3, 9.0])
    g = np.array(["A", "A", "A", "B"])
    r = shrink(y, g, tau2=4, sigma2=4)
    assert r["weight"] == pytest.approx([4 / (4 + 4 / 3), 4 / (4 + 4)])
    assert list(r["n"]) == [3, 1]
    # overall mean weighted by 1 / (tau2 + sigma2 / n): (3/16 x 2 + 1/8 x 9) / (5/16) = 4.8, not 3.75
    assert r["mu"] == pytest.approx(4.8)


def test_reml_on_a_balanced_design_gives_the_anova_estimates_and_ml_gives_less():
    r = fit(Y, np.empty((9, 0)), G)
    assert (r["tau2"], r["sigma2"]) == pytest.approx((4, 1), rel=1e-4)
    assert r["coef"]["const"] == pytest.approx(11 / 3)
    assert r["random_effects"]["A"] == pytest.approx(-20 / 13, rel=1e-4)  # 83/39 - 11/3
    # ML divides the between sum of squares by G, not G - 1: (26 / 3 - 1) / 3 = 23/9
    assert fit(Y, np.empty((9, 0)), G, reml=False)["tau2"] == pytest.approx(23 / 9, rel=1e-4)


def _draw(seed, groups, n):
    rng = np.random.default_rng(seed)
    return rng, np.repeat(np.arange(groups), n)


def test_with_the_group_means_added_the_slope_is_the_within_group_slope():
    rng, g = _draw(0, 30, 6)
    a = rng.normal(0, 1, 30)
    x = a[g] + rng.normal(0, 1, len(g))  # x is higher where the group effect is higher
    y = 0.5 * x + 2 * a[g] + rng.normal(0, 1, len(g))
    xd = x - group_means(x[:, None], g)[:, 0]
    yd = y - group_means(y[:, None], g)[:, 0]
    within = (xd @ yd) / (xd @ xd)
    r = fit(y, x[:, None], g, names=["x"], mundlak=True)
    assert r["coef"]["x"] == pytest.approx(within, rel=1e-6)
    assert abs(fit(y, x[:, None], g, names=["x"])["coef"]["x"] - within) > 0.01  # random intercept alone mixes in between


def test_a_covariate_measured_per_group_has_a_larger_se_than_rows_suggest():
    rng, g = _draw(1, 40, 25)
    z = rng.normal(0, 1, 40)[g]
    y = rng.normal(0, 1, 40)[g] + rng.normal(0, 1, len(g))
    r = fit(y, z[:, None], g, names=["z"])
    assert r["se"]["z"] > 2.5 * r["se_ols"]["z"]


def test_a_random_slope_widens_the_se_of_the_mean_slope():
    rng, g = _draw(2, 40, 20)
    x = rng.normal(0, 1, len(g))
    y = rng.normal(0, 0.5, 40)[g] * x + rng.normal(0, 1, 40)[g] + rng.normal(0, 1, len(g))
    ri = fit(y, x[:, None], g, names=["x"])
    rs = fit(y, x[:, None], g, names=["x"], random_slope=["x"])
    assert rs["se"]["x"] > 2 * ri["se"]["x"]
    assert rs["slope_var"]["x"] == pytest.approx(0.25, abs=0.15)


def test_an_upper_level_left_out_makes_its_covariate_look_too_certain():
    rng = np.random.default_rng(3)
    pref = np.repeat(np.arange(20), 60)
    muni = np.repeat(np.arange(120), 10)
    z = rng.normal(0, 1, 20)[pref]
    y = rng.normal(0, 1, 20)[pref] + rng.normal(0, 0.7, 120)[muni] + rng.normal(0, 1, 1200)
    only_muni = fit(y, z[:, None], muni, names=["z"])
    nested = fit(y, z[:, None], pref, names=["z"], nested=muni)
    assert nested["se"]["z"] > 1.5 * only_muni["se"]["z"]
    assert nested["nested_var"] == pytest.approx(0.49, abs=0.2)
    assert sum(nested["share"].values()) == pytest.approx(1)


def test_partial_pooling_is_closer_to_the_truth_than_raw_means_for_small_groups():
    rng = np.random.default_rng(4)
    n = rng.choice([2, 3, 30, 100], 60)
    g = np.repeat(np.arange(60), n)
    true = 5 + rng.normal(0, 1, 60)
    y = true[g] + rng.normal(0, 3, len(g))
    r = fit(y, np.empty((len(y), 0)), g)
    s = shrink(y, g, r["tau2"], r["sigma2"])
    small = s["n"] <= 3
    raw_err = np.sqrt(np.mean((s["raw"] - true)[small] ** 2))
    pooled_err = np.sqrt(np.mean((s["pooled"] - true)[small] ** 2))
    assert pooled_err < 0.7 * raw_err


def test_lower_level_codes_are_read_within_each_group():
    # ward 1 of one city is not ward 1 of another: codes 0..5 repeated in every prefecture give the same fit
    rng = np.random.default_rng(3)
    pref = np.repeat(np.arange(20), 60)
    muni = np.repeat(np.arange(120), 10)
    y = rng.normal(0, 1, 20)[pref] + rng.normal(0, 0.7, 120)[muni] + rng.normal(0, 1, 1200)
    a = fit(y, np.empty((1200, 0)), pref, nested=muni)
    b = fit(y, np.empty((1200, 0)), pref, nested=muni % 6)
    assert b["nested_var"] == pytest.approx(a["nested_var"], rel=1e-6)
