"""uvx --python 3.12 --with numpy --with pytest pytest -q scripts/test_breach.py"""

import math

import numpy as np
import pytest

from breach import (excess_volume, froehlich, gev_lmoments, gev_quantile, gumbel_lmoments, gumbel_quantile, macdonald,
                    run_chain, spillway_capacity)


def test_froehlich_matches_the_hand_value():
    # V 382,000 m3, h 14.5 m: 0.607 x 382000^0.295 x 14.5^1.24
    assert froehlich(382000, 14.5) == pytest.approx(0.607 * 382000 ** 0.295 * 14.5 ** 1.24)
    assert 735 < froehlich(382000, 14.5) < 745


def test_macdonald_form():
    assert macdonald(1000, 10) == pytest.approx(1.154 * 10000 ** 0.412)


def test_rational_formula_units():
    # 100 mm/h on 1 km2 with f = 1 is 100e-3 m x 1e6 m2 / 3600 s = 27.8 m3/s
    assert spillway_capacity(1.0, 100, 1.0, margin=1.0) == pytest.approx(100e-3 * 1e6 / 3600)
    assert spillway_capacity(0.7, 100, 0.5) == pytest.approx(1.2 * 0.7 * 100 * 0.5 / 3.6)


def test_excess_volume_is_the_triangle_above_the_outflow():
    v, qp, qc = 50000.0, 100.0, 30.0
    t = 2 * v / qp                                   # base of the triangle, peak at t/2
    ts = np.linspace(0, t, 200001)
    q = np.where(ts <= t / 2, qp * ts / (t / 2), qp * (t - ts) / (t / 2))
    numeric = np.trapezoid(np.maximum(q - qc, 0), ts)
    assert excess_volume(v, qp, qc) == pytest.approx(numeric, rel=1e-4)
    assert excess_volume(v, 10.0, 30.0) == 0.0


def test_gumbel_lmoments_recovers_known_parameters():
    rng = np.random.default_rng(0)
    mu, beta = 40.0, 12.0
    x = mu - beta * np.log(-np.log(rng.random(200000)))
    m, b = gumbel_lmoments(x)
    assert m == pytest.approx(mu, rel=0.01) and b == pytest.approx(beta, rel=0.01)
    assert gumbel_quantile(mu, beta, 200) == pytest.approx(mu - beta * math.log(-math.log(1 - 1 / 200)))


P = dict(f=0.7, r=100.0, margin=1.2, freeboard=1.0, max_dist=1000.0, peak=froehlich)


def pond(v, h, s, a, dist):
    return dict(v=v, h=h, s=s, a=a, dist=dist)


def test_a_large_pond_over_two_small_ones_breaks_both():
    ponds = {1: pond(100000, 10, 30000, 0.5, 300), 2: pond(2000, 4, 2000, 0.6, 300), 3: pond(3000, 4, 3000, 0.7, 2000),
             4: pond(1000, 3, 1000, 0.8, None)}
    down = {1: 2, 2: 3, 3: 4, 4: None}            # pond 4 is 2 km below pond 3, beyond the 1 km limit
    failed, why = run_chain(1, down, ponds, P)
    assert failed == [2, 3] and why == "next pond beyond the distance"


def test_a_large_pond_below_holds():
    ponds = {1: pond(5000, 4, 1000, 0.1, 300), 2: pond(500000, 10, 200000, 2.0, 300)}
    failed, why = run_chain(1, {1: 2, 2: None}, ponds, P)
    assert failed == [] and why == "next pond holds"


def test_a_pond_without_surface_stops_the_chain():
    ponds = {1: pond(100000, 10, 30000, 0.5, 300), 2: pond(2000, 4, None, 0.6, 300)}
    failed, why = run_chain(1, {1: 2, 2: None}, ponds, P)
    assert failed == [] and why == "next pond has no water surface"


def test_gev_lmoments_recovers_a_heavy_tail():
    rng = np.random.default_rng(1)
    xi, alpha, k = 30.0, 10.0, -0.15                  # k < 0: heavier upper tail than Gumbel
    u = rng.random(200000)
    x = xi + alpha * (1 - (-np.log(u)) ** k) / k
    a, b, c = gev_lmoments(x)
    assert a == pytest.approx(xi, rel=0.02) and b == pytest.approx(alpha, rel=0.03) and c == pytest.approx(k, abs=0.02)
    assert gev_quantile(xi, alpha, k, 200) > gumbel_quantile(*gumbel_lmoments(x), 200)
