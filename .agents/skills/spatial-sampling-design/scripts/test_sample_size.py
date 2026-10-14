"""uvx --with scipy --with pytest pytest test_sample_size.py

Expected values are worked out by hand with z = 1.96 for 95 % (1.959964 in the code).
"""

import pytest

from sample_size import (design_effect, effective_n, margin_of_mean, n_mean, n_proportion, n_stratified,
                         pilot_sd_upper, plan)


def test_n_for_a_mean_comes_from_the_spread_and_the_margin_not_a_fixed_number():
    assert n_mean(sd=10, margin=2) == pytest.approx((1.959964 * 10 / 2) ** 2, rel=1e-5)  # 96.04
    assert n_mean(sd=10, margin=1) == pytest.approx(4 * n_mean(sd=10, margin=2))  # half the margin, 4 times n
    assert n_mean(sd=20, margin=2) == pytest.approx(4 * n_mean(sd=10, margin=2))
    assert n_mean(sd=10, margin=2, confidence=0.90) == pytest.approx((1.644854 * 10 / 2) ** 2, rel=1e-5)


def test_n_for_a_proportion_is_largest_at_one_half():
    assert n_proportion(margin=0.05) == pytest.approx(1.959964**2 * 0.25 / 0.0025, rel=1e-5)  # 384.1
    assert n_proportion(margin=0.05, p=0.1) == pytest.approx(1.959964**2 * 0.09 / 0.0025, rel=1e-5)  # 138.3


def test_finite_population_correction_shrinks_n_for_a_small_frame():
    r = plan(n_proportion(margin=0.05), population=1000)
    assert r["after_population"] == pytest.approx(384.146 / (1 + 383.146 / 1000), rel=1e-4)  # 277.8
    assert r["n"] == 278
    assert plan(n_proportion(margin=0.05), population=10**9)["n"] == 385  # a huge frame changes nothing


def test_cluster_design_effect_and_effective_sample_size():
    assert design_effect(cluster_size=10, icc=0.1) == pytest.approx(1.9)
    assert design_effect(cluster_size=10, icc=0.0) == pytest.approx(1.0)
    assert design_effect(cluster_size=10, icc=1.0) == pytest.approx(10.0)  # every site repeats its cluster
    assert effective_n(200, design_effect(10, 0.1)) == pytest.approx(200 / 1.9)


def test_plan_multiplies_by_the_design_effect_then_allows_for_sites_that_cannot_be_measured():
    r = plan(n_mean(sd=10, margin=2), deff=1.9, response=0.8)
    assert r["after_deff"] == pytest.approx(96.036 * 1.9, rel=1e-4)  # 182.5
    assert r["n"] == 229  # 182.5 / 0.8 = 228.1, rounded up
    assert r["expected_measured"] == pytest.approx(229 * 0.8)


def test_stratification_needs_fewer_sites_when_strata_differ():
    # two equal strata, means 40 and 60, sds 4 and 12: within-stratum variance 80, overall variance 80 + 100
    srs = n_mean(sd=180 ** 0.5, margin=2)
    total, per = n_stratified(weights=[0.5, 0.5], sds=[4, 12], margin=2)
    assert srs == pytest.approx(1.959964**2 * 180 / 4, rel=1e-5)  # 172.9
    assert total == pytest.approx(1.959964**2 * 80 / 4, rel=1e-5)  # 76.8
    assert per == pytest.approx([total / 2, total / 2])
    total, per = n_stratified(weights=[0.5, 0.5], sds=[4, 12], margin=2, allocation="neyman")
    assert total == pytest.approx(1.959964**2 * 64 / 4, rel=1e-5)  # (0.5 x 4 + 0.5 x 12)^2 = 64
    assert per == pytest.approx([total * 2 / 8, total * 6 / 8])  # in proportion to W x S


def test_a_pilot_sd_is_raised_to_an_upper_confidence_limit():
    # 80 % upper limit from 10 pilot sites: sqrt(9 / chi2_0.20(9)), chi2_0.20(9) = 5.380 from a table
    assert pilot_sd_upper(sd=10, n=10, level=0.8) == pytest.approx(10 * (9 / 5.380) ** 0.5, rel=1e-3)
    assert pilot_sd_upper(sd=10, n=1000, level=0.8) == pytest.approx(10, rel=0.05)


def test_margin_of_a_given_n_inverts_n_mean():
    assert margin_of_mean(sd=10, n=n_mean(sd=10, margin=2)) == pytest.approx(2)


def test_bad_inputs_stop():
    with pytest.raises(ValueError):
        n_mean(sd=10, margin=0)
    with pytest.raises(ValueError):
        plan(100, response=0)
    with pytest.raises(ValueError):
        n_stratified(weights=[0.5, 0.4], sds=[1, 1], margin=1)
