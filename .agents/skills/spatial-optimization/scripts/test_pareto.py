"""uvx --with numpy --with scipy --with duckdb --with pytest pytest test_pareto.py"""

import itertools

import numpy as np
import pytest

from pareto import _value, epsilon_front, front, weighted


def _problem(seed, n=14, m=7):
    rng = np.random.default_rng(seed)
    d = rng.integers(1, 20, (n, m)).astype(float)
    w = rng.integers(1, 6, n).astype(float)
    return d, w


def _brute_front(d, w, p, radius):
    return front([_value(d, w, list(c), radius) for c in itertools.combinations(range(d.shape[1]), p)])


def test_front_by_hand():
    pts = [(10, 5), (12, 7), (11, 5), (9, 3), (12, 6), (15, 7)]
    assert front(pts) == [(9, 3), (10, 5), (12, 7)]


@pytest.mark.parametrize("seed", range(4))
def test_epsilon_constraints_find_the_whole_front_found_by_enumeration(seed):
    d, w = _problem(seed)
    exact = _brute_front(d, w, 2, 6)
    ours = [(a, b) for a, b, _ in epsilon_front(d, w, 2, 6)]
    assert ours == exact


def _supported(points):
    """Points on the lower-left convex hull of (distance, -coverage): reachable by some weighted sum."""
    pts = sorted(points)
    out = []
    for p_ in pts:
        others = [q for q in pts if q != p_]
        ok = False
        for lam in np.linspace(0, 50, 2001):
            score = lambda t: t[0] - lam * t[1]
            if all(score(p_) <= score(q) + 1e-9 for q in others):
                ok = True
                break
        if ok:
            out.append(p_)
    return out


def test_weighted_sums_miss_the_points_in_a_dent_of_the_front():
    # Search a few worlds for a front with a non-supported point; weighted sums over a fine grid of lambda never
    # return it, epsilon constraints do.
    for seed in range(40):
        d, w = _problem(seed)
        exact = _brute_front(d, w, 2, 6)
        supported = _supported(exact)
        if len(supported) < len(exact):
            break
    else:
        pytest.skip("no world with a non-supported Pareto point")
    found = {tuple(_value(d, w, weighted(d, w, 2, 6, lam), 6)) for lam in np.linspace(0, 50, 101)}
    dents = set(exact) - set(supported)
    assert not (dents & found)
    assert set([(a, b) for a, b, _ in epsilon_front(d, w, 2, 6)]) >= dents
