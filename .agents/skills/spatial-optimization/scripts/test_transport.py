"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pytest pytest test_transport.py"""

import itertools

import numpy as np
import pytest

from transport import nearest_cost, solve


def test_a_small_problem_by_hand():
    # Two origins (demand 3 and 2), two facilities (capacity 4 and 4). Origin 0 is 1 from A and 5 from B,
    # origin 1 is 2 from A and 3 from B. Uncapacitated, both go to A (cost 3 + 4 = 7) and A's capacity 4 < 5:
    # one unit moves to B. Moving origin 1's unit costs 3 - 2 = 1, origin 0's costs 4: optimum 7 + 1 = 8.
    C = np.array([[1.0, 5.0], [2.0, 3.0]])
    r = solve(C, [3, 2], [4, 4])
    assert r["cost"] == pytest.approx(8.0)
    np.testing.assert_allclose(r["flows"], [[3, 0], [1, 1]], atol=1e-9)
    # A is full: one more unit of A's capacity lets origin 1's unit come back from B: saves 1
    assert r["capacity_price"].tolist() == pytest.approx([1.0, 0.0])
    assert nearest_cost(C, [3, 2]) == pytest.approx(7.0)


def _random(seed, n=12, m=4):
    rng = np.random.default_rng(seed)
    C = rng.integers(1, 30, (n, m)).astype(float)
    d = rng.integers(1, 10, n).astype(float)
    s = np.full(m, np.ceil(d.sum() * 1.1 / m))
    return C, d, s


def _slopes(f, x, k, h=1e-3):
    """One-sided slopes of f in coordinate k: (f(x) - f(x - h e_k)) / h and (f(x + h e_k) - f(x)) / h."""
    lo, hi = x.copy(), x.copy()
    lo[k] -= h
    hi[k] += h
    return (f(x) - f(lo)) / h, (f(hi) - f(x)) / h


@pytest.mark.parametrize("seed", range(5))
def test_duals_are_slopes_of_the_total_cost(seed):
    # With integer data the problem is degenerate and a dual is one of many: it lies between the one-sided
    # slopes. (Measured: an origin price of 18 where the right-hand slope was 19.)
    C, d, s = _random(seed)
    r = solve(C, d, s)
    for j in range(len(s)):
        left, right = _slopes(lambda v: solve(C, d, v)["cost"], s, j)
        assert min(left, right) - 1e-6 <= -r["capacity_price"][j] <= max(left, right) + 1e-6
        if r["spare"][j] > 1e-9:
            assert r["capacity_price"][j] == pytest.approx(0.0, abs=1e-9)
    for i in range(len(d)):
        left, right = _slopes(lambda v: solve(C, v, s)["cost"], d, i)
        assert min(left, right) - 1e-6 <= r["origin_price"][i] <= max(left, right) + 1e-6


def test_duals_equal_both_slopes_when_the_problem_is_not_degenerate():
    rng = np.random.default_rng(11)
    C = rng.uniform(1, 30, (10, 4))
    d = rng.uniform(1, 10, 10)
    s = np.array([d.sum() * 0.2, d.sum() * 0.3, d.sum() * 0.25, d.sum() * 0.35])
    r = solve(C, d, s)
    for j in range(4):
        left, right = _slopes(lambda v: solve(C, d, v)["cost"], s, j)
        assert -r["capacity_price"][j] == pytest.approx(left, abs=1e-6) == pytest.approx(right, abs=1e-6)
    for i in range(10):
        left, right = _slopes(lambda v: solve(C, v, s)["cost"], d, i)
        assert r["origin_price"][i] == pytest.approx(left, abs=1e-6)
        assert r["origin_price"][i] == pytest.approx(right, abs=1e-6)


def test_integer_inputs_give_integer_flows():
    for seed in range(5):
        C, d, s = _random(seed)
        np.testing.assert_allclose(solve(C, d, s)["flows"], np.round(solve(C, d, s)["flows"]), atol=1e-9)


def test_the_lp_matches_enumeration_of_every_assignment_on_a_tiny_problem():
    # Three origins of one unit each, two facilities of capacity 2: every assignment of origins to facilities
    # that respects the capacities, by brute force.
    rng = np.random.default_rng(9)
    C = rng.uniform(0, 10, (3, 2))
    best = min(sum(C[i, j] for i, j in enumerate(a)) for a in itertools.product(range(2), repeat=3)
               if max(a.count(0), a.count(1)) <= 2)
    assert solve(C, [1, 1, 1], [2, 2])["cost"] == pytest.approx(best)


def test_short_capacity_stops():
    with pytest.raises(SystemExit):
        solve(np.ones((2, 2)), [3, 3], [2, 2])


def test_loose_capacity_is_the_nearest_assignment():
    C, d, s = _random(3)
    r = solve(C, d, np.full(len(s), d.sum()))
    assert r["cost"] == pytest.approx(nearest_cost(C, d))
    assert np.allclose(r["capacity_price"], 0)
