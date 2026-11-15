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
