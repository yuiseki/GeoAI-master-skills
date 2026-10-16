"""uvx --with numpy --with scipy --with duckdb --with pytest pytest test_facility_location.py"""

import itertools

import numpy as np
import pytest

from facility_location import (
    coverage_heuristic,
    coverage_milp,
    coverage_value,
    pmedian_heuristic,
    pmedian_milp,
    pmedian_value,
    solve,
)


def problem(n=30, m=9, seed=0):
    rng = np.random.default_rng(seed)
    demand = rng.uniform(0, 10, size=(n, 2))
    cand = rng.uniform(0, 10, size=(m, 2))
    d = np.linalg.norm(demand[:, None, :] - cand[None, :, :], axis=2) * 1000
    w = rng.integers(1, 100, size=n).astype(float)
    return d, w


def brute(d, w, p, value):
    best = None
    for combo in itertools.combinations(range(d.shape[1]), p):
        v = value(d, w, list(combo))
        if best is None or v < best[0]:
            best = (v, combo)
    return best


@pytest.mark.parametrize("seed", range(3))
def test_pmedian_milp_matches_brute_force_and_beats_the_heuristic(seed):
    d, w = problem(seed=seed)
    opt, _ = brute(d, w, 3, pmedian_value)
    milp = pmedian_milp(d, w, 3)
    heur = pmedian_heuristic(d, w, 3)
    assert milp["status"] == "optimal"
    assert pmedian_value(d, w, milp["open"]) == pytest.approx(opt)
    assert pmedian_value(d, w, heur["open"]) >= opt - 1e-6


@pytest.mark.parametrize("seed", range(3))
def test_coverage_milp_matches_brute_force(seed):
    d, w = problem(seed=seed)
    radius = 2500.0
    opt = -brute(d, w, 3, lambda d, w, o: -coverage_value(d, w, o, radius))[0]
    milp = coverage_milp(d, w, 3, radius)
    heur = coverage_heuristic(d, w, 3, radius)
    assert coverage_value(d, w, milp["open"], radius) == pytest.approx(opt)
    assert coverage_value(d, w, heur["open"], radius) <= opt + 1e-6


def test_solve_recomputes_the_objective_and_checks_against_the_heuristic():
    d, w = problem(seed=4)
    out = solve(d, w, 3, problem_kind="p-median")
    assert out["milp"]["recomputed"] == pytest.approx(out["milp"]["objective"], rel=1e-6)
    assert out["milp"]["recomputed"] <= out["heuristic"]["recomputed"] + 1e-6
    assert len(out["milp"]["open"]) == 3


def test_a_demand_no_candidate_can_reach_stops_the_run():
    d, w = problem(seed=5)
    d[0, :] = np.inf
    with pytest.raises(SystemExit):
        solve(d, w, 3, problem_kind="p-median")


def test_a_milp_that_does_worse_than_the_heuristic_is_reported_as_a_model_error(monkeypatch):
    import facility_location as fl

    d, w = problem(seed=6)
    # Stand in for a wrongly built model: it reports the true value of the sites it chose, so the
    # objective check passes, but the sites are the worst ones. Only the comparison with the
    # heuristic can catch it.
    def wrong_model(d, w, p):
        worst = list(np.argsort(-(w[:, None] * d).sum(axis=0))[:p])
        return {"status": "optimal", "open": worst, "objective": fl.pmedian_value(d, w, worst)}

    monkeypatch.setattr(fl, "pmedian_milp", wrong_model)
    with pytest.raises(SystemExit):
        fl.solve(d, w, 3, problem_kind="p-median")


def test_distance_unit_follows_the_column_suffix():
    import facility_location as fl
    assert fl.distance_unit("distance_km") == "km"
    assert fl.distance_unit("network_m") == "m"
    assert fl.distance_unit("dist") == "m"


# Bounds and baselines

@pytest.mark.parametrize("seed", range(4))
def test_the_lp_relaxation_bounds_the_optimum(seed):
    from facility_location import lp_bound

    d, w = problem(seed=seed)
    opt_pm, _ = brute(d, w, 3, pmedian_value)
    assert lp_bound(d, w, 3) <= opt_pm + 1e-6
    radius = np.percentile(d, 25)
    best_cov = max(coverage_value(d, w, list(c), radius) for c in itertools.combinations(range(d.shape[1]), 3))
    assert lp_bound(d, w, 3, "coverage", radius) >= best_cov - 1e-6


def test_random_baseline_matches_the_exact_distribution_over_every_choice():
    # 9 candidates, p 3: 84 choices. The share of random draws at least as good as a given configuration
    # converges to its share among all 84.
    from facility_location import random_baseline, standing

    d, w = problem(seed=5)
    every = np.array([pmedian_value(d, w, list(c)) for c in itertools.combinations(range(9), 3)])
    some = [0, 4, 7]
    exact = np.mean(every <= pmedian_value(d, w, some))
    base = random_baseline(d, w, 3, draws=20000, seed=1)
    assert standing(pmedian_value(d, w, some), base) == pytest.approx(exact, abs=0.01)
    assert standing(every.min(), base) == pytest.approx(1 / 84, abs=0.004)  # only the optimum itself


def test_the_lp_relaxation_can_be_strictly_loose():
    # Integer distances 1-9, unit weights, 12 demand points, 8 candidates (found by search): the relaxation opens
    # fractions of sites and goes below (p-median) or above (coverage) every integer choice.
    from facility_location import lp_bound

    def world(seed):
        rng = np.random.default_rng(seed)
        return rng.integers(1, 10, (12, 8)).astype(float), np.ones(12)

    d, w = world(6)
    opt = min(pmedian_value(d, w, list(c)) for c in itertools.combinations(range(8), 2))
    assert (opt, lp_bound(d, w, 2)) == (34.0, pytest.approx(33.0))
    d, w = world(4)
    best = max(coverage_value(d, w, list(c), 4) for c in itertools.combinations(range(8), 2))
    assert (best, lp_bound(d, w, 2, "coverage", 4)) == (9.0, pytest.approx(9.5))
