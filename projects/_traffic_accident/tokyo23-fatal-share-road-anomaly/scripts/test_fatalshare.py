import itertools

import numpy as np
import pytest
from scipy.stats import binom

import fatalshare as fs


def brute_sf(p, k):
    tot = 0.0
    for bits in itertools.product([0, 1], repeat=len(p)):
        if sum(bits) >= k:
            tot += np.prod([pi if b else 1 - pi for pi, b in zip(p, bits)])
    return tot


def test_poibin_sf_matches_binomial_and_brute_force():
    assert fs.poibin_sf(np.full(30, 0.1), 4) == pytest.approx(binom.sf(3, 30, 0.1), rel=1e-10)
    p = np.array([0.01, 0.3, 0.5, 0.02, 0.9, 0.2])
    for k in range(0, 8):
        assert fs.poibin_sf(p, k) == pytest.approx(brute_sf(p, k), abs=1e-12)
    assert fs.poibin_sf(p, 0) == 1.0
    assert fs.poibin_sf(np.array([]), 1) == 0.0


def test_poibin_sf_tiny_tail_is_not_rounded_to_zero_or_negative():
    v = fs.poibin_sf(np.full(200, 0.004), 6)
    assert 0 < v < 1e-3
    assert v == pytest.approx(binom.sf(5, 200, 0.004), rel=1e-8)


def test_mesh_codes_known_points():
    # 3rd mesh 53394611 spans lat 35.675-35.68333, lon 139.7625-139.775
    lat, lon = np.array([35.6760, 35.6820, 35.6760, 35.6820]), np.array([139.7630, 139.7630, 139.7740, 139.7740])
    assert list(fs.mesh_code(lat, lon, 3)) == ["53394611"] * 4
    # 500 m: 1 SW, 2 SE, 3 NW, 4 NE
    assert list(fs.mesh_code(lat, lon, 4)) == ["533946111", "533946113", "533946112", "533946114"]
    # 250 m: the SW quarter of the SW 500 m mesh
    assert fs.mesh_code(np.array([35.6755]), np.array([139.7630]), 5)[0] == "5339461111"
    assert fs.mesh_code(np.array([35.6785]), np.array([139.7680]), 5)[0] == "5339461114"


def test_mesh_parent():
    assert fs.mesh_parent("5339461114", 4) == "533946111"
    assert fs.mesh_parent("5339461114", 3) == "53394611"


def test_merge_small_strata_walks_up_the_hierarchy():
    # level keys: (shape, width, median); min_n = 3
    keys = [("A", "w1", "m1")] * 5 + [("A", "w1", "m2")] * 1 + [("A", "w2", "m1")] * 1 + [("B", "w3", "m1")] * 1
    lab = fs.merge_strata(keys, min_n=3)
    assert lab[:5] == ["A|w1|m1"] * 5
    # A|w1|m2 (1) -> A|w1 left with 1 -> A gets it and A|w2 (1) = 2 -> '*' with B (1)
    assert lab[5:] == ["*"] * 3


def test_leave_unit_out_rates():
    stratum = np.array(["s", "s", "s", "s", "t", "t"])
    unit = np.array(["u1", "u1", "u2", "u2", "u1", "u2"])
    fatal = np.array([1, 0, 0, 0, 1, 1])
    parent = {"s": "*", "t": "*"}
    p = fs.leave_unit_out_p(stratum, unit, fatal, parent)
    # u1 accidents use stratum s without u1: 0/2; t without u1: 1/1
    assert p.tolist() == [0.0, 0.0, 0.5, 0.5, 1.0, 1.0]


def test_leave_unit_out_falls_back_to_parent_when_unit_owns_the_stratum():
    stratum = np.array(["s", "t", "t"])
    unit = np.array(["u1", "u2", "u3"])
    fatal = np.array([1, 0, 1])
    p = fs.leave_unit_out_p(stratum, unit, fatal, {"s": "*", "t": "*"})
    # s is all u1 -> parent "*" without u1: 1/2
    assert p[0] == 0.5
    assert p[1] == 1.0 and p[2] == 0.0


def test_bh():
    q = fs.bh(np.array([0.01, 0.04, 0.03, 0.5]))
    assert q.tolist() == pytest.approx([0.04, 0.0533333333, 0.0533333333, 0.5])


def test_overdispersion_stat_zero_when_observed_equals_expected():
    unit = np.array([0, 0, 1, 1])
    p = np.array([0.5, 0.5, 0.5, 0.5])
    assert fs.overdispersion(unit, np.array([1, 0, 0, 1]), p) == pytest.approx(0.0)
    assert fs.overdispersion(unit, np.array([1, 1, 0, 0]), p) == pytest.approx(2 * 1 / 0.5)


def test_permute_within_strata_keeps_counts():
    rng = np.random.default_rng(0)
    stratum = np.array(list("aaabbbbcc"))
    fatal = np.array([1, 0, 0, 1, 1, 0, 0, 0, 1])
    for _ in range(20):
        f2 = fs.permute_within(stratum, fatal, rng)
        for s in "abc":
            assert f2[stratum == s].sum() == fatal[stratum == s].sum()


def test_merge_strata_leftover_of_a_parent_is_also_merged_up():
    # A|w1|m1 has 4 (kept); A|w1|m2 has 2 -> goes to A|w1, but A|w1 is then left with 2 rows (< 3) -> goes to A,
    # A then holds 2 + 1 (A|w2) = 3 -> kept
    keys = [("A", "w1", "m1")] * 4 + [("A", "w1", "m2")] * 2 + [("A", "w2", "m1")] * 1
    lab = fs.merge_strata(keys, min_n=3)
    assert lab == ["A|w1|m1"] * 4 + ["A"] * 3
    # every final stratum except '*' holds at least min_n rows
    from collections import Counter
    assert all(n >= 3 for s, n in Counter(lab).items() if s != "*")


def test_merge_strata_rows_reaching_the_top_are_labelled_all():
    keys = [("A", "w", "m")] * 5 + [("B", "w", "m")] * 1
    lab = fs.merge_strata(keys, min_n=3)
    assert lab[:5] == ["A|w|m"] * 5 and lab[5] == "*"


def test_poibin_k_needed():
    p = np.full(30, 0.1)
    k = fs.poibin_k_needed(p, 1e-3)
    assert binom.sf(k - 1, 30, 0.1) <= 1e-3 < binom.sf(k - 2, 30, 0.1)
    assert fs.poibin_k_needed(np.array([0.5]), 1e-3) == 2  # even 1 of 1 is not enough
