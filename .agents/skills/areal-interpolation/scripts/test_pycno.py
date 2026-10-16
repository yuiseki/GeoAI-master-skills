"""uvx --with numpy --with pytest pytest test_pycno.py"""

import numpy as np
import pytest

from pycno import area_weighted, pycno, to_targets


def _blocks(n, b, offset=0):
    """Labels of b x b blocks on an n x n grid, shifted by offset cells (cells past the grid's start get -1)."""
    r, c = np.indices((n, n))
    rr, cc = r - offset, c - offset
    lab = (rr // b) * ((n + b - 1) // b) + cc // b
    return np.where((rr >= 0) & (cc >= 0), lab, -1)


def test_every_source_keeps_its_count():
    rng = np.random.default_rng(0)
    zones = _blocks(24, 6)
    totals = {int(z): float(rng.uniform(10, 1000)) for z in np.unique(zones)}
    s, _ = pycno(zones, totals)
    for z, t in totals.items():
        assert s[zones == z].sum() == pytest.approx(t, rel=1e-9)
    assert (s >= 0).all()


def test_an_even_density_stays_flat():
    zones = _blocks(20, 5)
    totals = {int(z): 25.0 for z in np.unique(zones)}  # one per cell everywhere
    s, _ = pycno(zones, totals)
    np.testing.assert_allclose(s, 1.0, atol=1e-9)


def _backtest(truth, b=6, offset=3):
    n = truth.shape[0]
    zones = _blocks(n, b)
    targets = _blocks(n, b, offset)
    totals = {int(z): float(truth[zones == z].sum()) for z in np.unique(zones)}
    true_t = to_targets(truth, targets)
    s, _ = pycno(zones, totals)
    pt, aw = to_targets(s, targets), area_weighted(zones, totals, targets)
    err = lambda d: np.sqrt(np.mean([(d[t] - true_t[t]) ** 2 for t in true_t]))
    return err(pt), err(aw)


def test_a_smooth_surface_is_recovered_better_than_by_even_spread():
    g = np.arange(36)
    X, Y = np.meshgrid(g, g)
    truth = 50 + 40 * np.sin(X / 6) * np.cos(Y / 7)
    e_p, e_a = _backtest(truth)
    assert e_p < 0.5 * e_a


def test_counts_in_one_corner_of_each_zone_are_not_recovered_better():
    # Everything sits in each source's top-left cell: no smooth surface puts it there.
    truth = np.zeros((36, 36))
    truth[::6, ::6] = 100.0
    e_p, e_a = _backtest(truth)
    assert e_p > 0.8 * e_a


def test_the_two_edge_rules_differ_next_to_a_gap():
    zones = _blocks(20, 5)
    zones[8:12, 8:12] = -1  # a hole (a lake)
    totals = {int(z): float((zones == z).sum()) * (1 + (z % 3)) for z in np.unique(zones[zones >= 0])}
    a, _ = pycno(zones, totals, edge="neumann")
    b, _ = pycno(zones, totals, edge="mean")
    ring = np.zeros_like(zones, bool)
    ring[7, 8:12] = ring[12, 8:12] = ring[8:12, 7] = ring[8:12, 12] = True
    assert b[ring].mean() < a[ring].mean()  # the "mean" rule counts the hole as 0 and pulls its edge down
