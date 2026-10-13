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
