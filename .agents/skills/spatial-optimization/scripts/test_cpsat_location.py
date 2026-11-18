"""uvx --with numpy --with ortools --with duckdb --with pytest pytest test_cpsat_location.py"""

import itertools

import numpy as np
import pytest

from cpsat_location import (
    cflp_heuristic,
    cflp_recompute,
    solve_cflp,
    solve_schedule,
)


def test_cflp_hand_calculated_indivisible_demand():
    # Two demands (3, 2) and two facilities (cap 4, 4). Costs [[1, 5], [2, 3]].
    # If divisible (LP), cost is 8 (demand 1 splits 1+1).
    # Single-source (indivisible): demand 0 (3) -> site 0 (cost 3), demand 1 (2) -> site 1 (cost 6), total = 9.
    d = np.array([[1.0, 5.0], [2.0, 3.0]])
    w = np.array([3.0, 2.0])
    s = np.array([4.0, 4.0])
    res = solve_cflp(d, w, s, p=2, scale=10)
    assert res["status"] == "optimal"
    assert res["recomputed"] == pytest.approx(9.0)
    assert res["assign"] == [0, 1]


def test_cflp_infeasible_even_when_total_capacity_exceeds_total_demand():
    # Three demands of weight 3 (total 9) and two facilities of capacity 5 (total 10).
    # Total capacity >= total demand, yet no single-source assignment fits (at most one demand per facility).
    d = np.ones((3, 2))
    w = np.array([3.0, 3.0, 3.0])
    s = np.array([5.0, 5.0])
    with pytest.raises(SystemExit):
        solve_cflp(d, w, s, p=2)


def _brute_cflp(d, w, s, p, fc=None):
    n, m = d.shape
    best = np.inf
    for open_sites in itertools.combinations(range(m), p):
        open_list = list(open_sites)
        for assign in itertools.product(open_list, repeat=n):
            try:
                val, _ = cflp_recompute(d, w, s, open_list, assign, fc)
                if val < best:
                    best = val
            except ValueError:
                continue
    return best


@pytest.mark.parametrize("seed", range(4))
def test_cflp_matches_brute_force_and_beats_heuristic(seed):
    rng = np.random.default_rng(seed)
    n, m, p = 6, 4, 2
    dem_xy = rng.uniform(0, 10, (n, 2))
    fac_xy = rng.uniform(0, 10, (m, 2))
    d = np.round(np.linalg.norm(dem_xy[:, None, :] - fac_xy[None, :, :], axis=2), 2)
    w = rng.integers(1, 5, size=n).astype(float)
    s = np.full(m, float(np.ceil(w.sum() * 0.75)))
    fc = rng.uniform(5, 15, size=m).round(2)

    opt = _brute_cflp(d, w, s, p, fc)
    assert np.isfinite(opt)
    res = solve_cflp(d, w, s, p, fixed_cost=fc, scale=100)
    assert res["status"] == "optimal"
    assert res["recomputed"] == pytest.approx(opt, abs=1e-4)
    if res["heuristic"] is not None:
        assert res["recomputed"] <= res["heuristic"]["recomputed"] + 1e-4


def test_cflp_recompute_catches_capacity_violation():
    d = np.array([[1.0, 2.0], [1.0, 2.0]])
    w = np.array([3.0, 3.0])
    s = np.array([4.0, 4.0])
    with pytest.raises(ValueError, match="exceeds capacity"):
        cflp_recompute(d, w, s, [0], [0, 0])


def test_schedule_respects_time_windows_and_travel():
    # Depot = 0, Task A (idx 0 -> node 1), Task B (idx 1 -> node 2)
    # Travel: 0->1 = 10, 0->2 = 10, 1->2 = 5, 2->1 = 5
    # Task B has an early window [0, 15] (dur 10), Task A has a later window [20, 40] (dur 10).
    # One team must visit B first (start=10, end=20), then travel 5 to A (start=25, end=35), then return (10).
    # Total travel = 10 + 5 + 10 = 25.
    tasks = [
        {"id": "A", "start_min": 20, "end_max": 40, "duration": 10},
        {"id": "B", "start_min": 0, "end_max": 15, "duration": 10},
    ]
    T = np.array([
        [0, 10, 10],
        [10, 0, 5],
        [10, 5, 0],
    ])
    res = solve_schedule(tasks, T, num_teams=1)
    assert res["status"] == "optimal"
    assert res["total_travel"] == 25
    stops = res["routes"][0]["stops"]
    assert [s["id"] for s in stops] == ["B", "A"]
    assert stops[0]["start"] == 10 and stops[0]["end"] == 20
    assert stops[1]["start"] == 25 and stops[1]["end"] == 35


def test_schedule_splits_across_two_teams_when_windows_conflict():
    # Two tasks both require start in [10, 15] with duration 20: impossible for 1 team.
    tasks = [
        {"id": "A", "start_min": 10, "end_max": 15, "duration": 20},
        {"id": "B", "start_min": 10, "end_max": 15, "duration": 20},
    ]
    T = np.array([
        [0, 5, 5],
        [5, 0, 5],
        [5, 5, 0],
    ])
    with pytest.raises(SystemExit):
        solve_schedule(tasks, T, num_teams=1)

    res2 = solve_schedule(tasks, T, num_teams=2)
    assert res2["status"] == "optimal"
    active_teams = [r for r in res2["routes"] if r["stops"]]
    assert len(active_teams) == 2
    assert res2["total_travel"] == 20


def test_rounding_slack_by_hand():
    from cpsat_location import rounding_slack
    # scale 10. Demand 0: 1.04 -> 1.0 (rounded down, adds nothing), 2.06 -> 2.1 (adds 0.04). Demand 1: 3.0 exact,
    # the unreachable site is ignored. Opening costs 0.57 -> 0.6 (adds 0.03), 0.69 -> 0.7 (adds 0.01), 0.2 exact;
    # p = 1 keeps the largest, 0.03.
    cost = np.array([[1.04, 2.06], [3.0, np.inf]])
    assert rounding_slack(cost, np.array([0.57, 0.69, 0.2]), 1, 10) == pytest.approx(0.04 + 0.03)


def test_cflp_exact_costs_leave_no_slack_and_no_gap_at_the_optimum():
    d = np.array([[1.0, 5.0], [2.0, 3.0]])
    res = solve_cflp(d, np.array([3.0, 2.0]), np.array([4.0, 4.0]), p=2, fixed_cost=np.array([0.5, 0.25]), scale=100)
    assert res["status"] == "optimal"
    assert res["rounding_slack"] == 0
    assert res["bound"] == pytest.approx(res["recomputed"]) and res["gap"] == pytest.approx(0, abs=1e-12)


def test_cflp_inexact_opening_costs_count_in_the_slack():
    d = np.array([[1.0, 5.0], [2.0, 3.0]])                # exact at scale 100
    res = solve_cflp(d, np.array([3.0, 2.0]), np.array([4.0, 4.0]), p=2, fixed_cost=np.array([0.506, 0.25]), scale=100)
    assert res["rounding_slack"] == pytest.approx(0.004)   # 0.506 -> 0.51


# The lower bound in the original units. CP-SAT solves a model whose costs are rounded to integers after scaling,
# so its bound holds for that model. Each cost term moves by at most 0.5 / scale, so subtracting that slack for
# every term a solution can use gives a bound for the original costs, as long as the capacities were not rounded.

def test_bound_report_by_hand():
    from cpsat_location import bound_report
    # scaled bound 1234 at scale 100 -> 12.34, minus a rounding slack of 0.025
    r = bound_report(1234, recomputed=12.50, slack=0.025, scale=100, exact_capacity=True)
    assert r["rounding_slack"] == pytest.approx(0.025)
    assert r["bound"] == pytest.approx(12.315)
    assert r["bound_scope"] == "original"
    assert r["gap"] == pytest.approx((12.50 - 12.315) / 12.50)


def test_bound_report_without_exact_capacities_does_not_claim_the_original():
    from cpsat_location import bound_report
    r = bound_report(1234, recomputed=12.50, slack=0.025, scale=100, exact_capacity=False)
    assert r["bound"] is None and r["gap"] is None
    assert r["bound_scope"] == "rounded_model"
    assert r["rounded_model_bound"] == pytest.approx(12.34)


@pytest.mark.parametrize("seed", range(4))
def test_cflp_bound_is_below_the_true_optimum_and_close_when_optimal(seed):
    rng = np.random.default_rng(seed)
    n, m, p = 6, 4, 2
    d = rng.uniform(0, 10, (n, m)).round(4)          # not multiples of 1/scale: the costs are rounded
    w = rng.integers(1, 5, size=n).astype(float)
    s = np.full(m, float(np.ceil(w.sum() * 0.75)))
    fc = rng.uniform(5, 15, size=m).round(3)
    opt = _brute_cflp(d, w, s, p, fc)
    res = solve_cflp(d, w, s, p, fixed_cost=fc, scale=100)
    assert res["bound_scope"] == "original"
    assert 0 < res["rounding_slack"] <= (n + p) * 0.5 / 100   # n assignments and p opening costs, 0.005 at most each
    assert res["bound"] <= opt + 1e-9
    assert res["bound"] <= res["recomputed"]
    assert res["status"] == "optimal"
    assert res["recomputed"] - res["bound"] <= (n + p) * 1.0 / 100 + 1e-9   # at most what rounding added and removed
    assert 0 <= res["gap"]


def test_cflp_fractional_capacities_leave_the_bound_on_the_rounded_model():
    d = np.array([[1.0, 5.0], [2.0, 3.0]])
    w = np.array([3.004, 2.0])                       # 300.4 at scale 100: the capacity rows are rounded
    s = np.array([5.5, 4.0])
    res = solve_cflp(d, w, s, p=2, scale=100)
    assert res["bound_scope"] == "rounded_model"
    assert res["bound"] is None and res["gap"] is None


def test_cflp_feasible_stop_reports_a_positive_gap():
    # A search stopped by the time limit: whatever it returns, its bound must not pass the solution, and a stop
    # before the proof leaves a gap above zero.
    rng = np.random.default_rng(7)
    n, m, p = 60, 25, 6
    d = rng.uniform(0, 100, (n, m)).round(3)
    w = rng.integers(1, 9, size=n).astype(float)
    s = np.full(m, float(np.ceil(w.sum() / p * 1.1)))
    res = solve_cflp(d, w, s, p, scale=100, time_limit_s=0.05, workers=1)
    assert res["bound"] <= res["recomputed"]
    if res["status"] == "feasible":
        assert res["gap"] > 0


def test_cflp_stops_when_a_feasible_solution_is_below_the_bound(monkeypatch):
    # A heuristic solution that is feasible for the original problem cannot be below a valid lower bound. If it is,
    # the model or its rounding is wrong, and the run stops instead of reporting the bound.
    import cpsat_location
    monkeypatch.setattr(cpsat_location, "cflp_heuristic",
                        lambda *a, **k: {"open": [0], "assign": [0, 0], "recomputed": 1.0})
    d = np.array([[1.0, 5.0], [2.0, 3.0]])
    with pytest.raises(SystemExit, match="below the lower bound"):
        cpsat_location.solve_cflp(d, np.array([3.0, 2.0]), np.array([4.0, 4.0]), p=2, scale=10)


def test_cflp_bound_survives_costs_rounded_up():
    # One demand, one site, cost 1.06 at scale 10: CP-SAT sees 11, i.e. 1.1. Its bound 1.1 is above the true optimum
    # 1.06, so the slack must take off what rounding added (0.04), not what it removed.
    res = solve_cflp(np.array([[1.06]]), np.array([1.0]), np.array([1.0]), p=1, scale=10)
    assert res["recomputed"] == pytest.approx(1.06)
    assert res["bound"] == pytest.approx(1.06) and res["bound"] <= res["recomputed"] + 1e-12
