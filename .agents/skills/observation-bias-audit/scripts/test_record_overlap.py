"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pytest pytest test_record_overlap.py"""

import numpy as np
import pytest

from record_overlap import chapman, match, overlap


def test_one_to_one_matching_by_hand():
    a = np.array([[0.0, 0], [10, 0], [100, 0]])
    b = np.array([[1.0, 0], [3, 0], [11, 0]])
    # a0-b0 (1), a0-b1 (3), a1-b1 (7), a1-b2 (1): shortest first, each point once: a0-b0, a1-b2
    assert sorted(match(a, b, 8)) == [(0, 0), (1, 2)]
    assert match(a, b, 0.5) == []


def test_chapman_by_hand():
    c = chapman(60, 50, 30)
    assert c["N"] == pytest.approx(61 * 51 / 31 - 1)
    assert c["se"] ** 2 == pytest.approx(61 * 51 * 30 * 20 / (31 ** 2 * 32))
    assert c["seen"] == 80


def _world(rng, N=600, p1=0.6, p2=0.5, catch=None):
    xy = rng.uniform(0, 20000, (N, 2))
    q = np.ones(N) if catch is None else catch(rng, N)
    in1 = rng.random(N) < np.minimum(p1 * q, 1)
    in2 = rng.random(N) < np.minimum(p2 * q, 1)
    jitter = lambda k: rng.normal(0, 10, (k, 2))  # each record places the item a little differently
    return xy[in1] + jitter(in1.sum()), xy[in2] + jitter(in2.sum()), xy


def test_independent_records_give_back_the_total_and_the_interval_covers():
    est, cover = [], 0
    for s in range(200):
        a, b, _ = _world(np.random.default_rng(s))
        r = overlap(a, b, 60)["all"]
        est.append(r["N"])
        cover += r["low"] <= 600 <= r["high"]
    assert np.mean(est) == pytest.approx(600, rel=0.02)
    assert cover / 200 > 0.9


def test_items_easy_for_both_records_make_the_estimate_too_small_and_strata_help_when_they_carry_it():
    # Half the area is well watched (both records catch items there with probability x 1.5), half poorly
    # (x 0.4): the dependence lies between the halves. Pooled, N comes out too small; summed over the halves,
    # nearly right.
    pooled, strat = [], []
    for s in range(100):
        rng = np.random.default_rng(1000 + s)
        xy = rng.uniform(0, 20000, (600, 2))
        q = np.where(xy[:, 0] < 10000, 1.5, 0.4)
        in1, in2 = rng.random(600) < 0.6 * q, rng.random(600) < 0.5 * q
        a, b = xy[in1], xy[in2]
        pooled.append(overlap(a, b, 1e-6)["all"]["N"])
        strat.append(overlap(a, b, 1e-6, a[:, 0] < 10000, b[:, 0] < 10000)["sum of strata"]["N"])
    assert np.mean(pooled) < 0.9 * 600
    assert np.mean(strat) == pytest.approx(600, rel=0.06)


def test_the_matching_radius_moves_the_estimate_both_ways():
    a, b, _ = _world(np.random.default_rng(7), N=2000)  # denser: false pairs at large radii
    est = {r: overlap(a, b, r)["all"]["N"] for r in (5, 60, 400)}
    assert est[5] > 1.3 * 2000  # true pairs 10-20 m apart are missed
    assert est[60] == pytest.approx(2000, rel=0.08)
    assert est[400] < 0.9 * 2000  # different items paired
