"""uvx --with numpy --with pyvroom --with duckdb --with pytest pytest test_vrp_routing.py"""

import itertools
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from vrp_routing import solve_vrp, vrp_recompute


def test_tsp_hand_calculated():
    # 0(デポ), 1, 2, 3 の対称距離行列。最適巡回は 0-1-2-3-0 (または逆順) で距離 1+1+1+1 = 4、対角は 10
    d = np.array(
        [
            [0, 1, 10, 1],
            [1, 0, 1, 10],
            [10, 1, 0, 1],
            [1, 10, 1, 0],
        ],
        dtype=float,
    )
    vehicles = [{"id": 1, "start": 0, "end": 0}]
    jobs = [
        {"id": 1, "location": 1},
        {"id": 2, "location": 2},
        {"id": 3, "location": 3},
    ]
    res = solve_vrp(d, vehicles, jobs)
    assert res["status"] == "ALL_SERVED"
    assert res["recompute"]["all_jobs_served"]
    assert res["total_duration"] == pytest.approx(4.0)


def test_cvrp_capacity_split():
    # 各顧客需要 4、車両容量 6 -> 1台には1顧客しか乗らず2台必要
    d = np.array(
        [
            [0, 5, 6],
            [5, 0, 1],
            [6, 1, 0],
        ],
        dtype=float,
    )
    vehicles = [
        {"id": 1, "start": 0, "end": 0, "capacity": 6},
        {"id": 2, "start": 0, "end": 0, "capacity": 6},
    ]
    jobs = [
        {"id": 1, "location": 1, "demand": 4},
        {"id": 2, "location": 2, "demand": 4},
    ]
    res = solve_vrp(d, vehicles, jobs)
    assert res["status"] == "ALL_SERVED"
    assert res["recompute"]["capacity_ok"]
    assert len(res["routes"]) == 2
    # 0-1-0 (10) + 0-2-0 (12) = 22
    assert res["total_duration"] == pytest.approx(22.0)


def test_vrptw_time_window_forces_order():
    # 0 -> 2 -> 1 -> 0 は距離 2+2+1=5、0 -> 1 -> 2 -> 0 は距離 1+2+2=5 だが
    # job 2 の時間枠が [0, 3]、job 1 の時間枠が [4, 10] なので 0 -> 2 -> 1 -> 0 のみ実行可能
    d = np.array(
        [
            [0, 1, 2],
            [1, 0, 2],
            [2, 2, 0],
        ],
        dtype=float,
    )
    vehicles = [{"id": 1, "start": 0, "end": 0, "time_window": (0, 20)}]
    jobs = [
        {"id": 1, "location": 1, "service": 1, "time_windows": [(4, 10)]},
        {"id": 2, "location": 2, "service": 1, "time_windows": [(0, 3)]},
    ]
    res = solve_vrp(d, vehicles, jobs)
    assert res["status"] == "ALL_SERVED"
    assert res["recompute"]["time_window_ok"]
    job_seq = [s["job_id"] for s in res["routes"][0]["steps"] if s["type"] == "job"]
    assert job_seq == [2, 1]


def test_vrp_unassigned_when_capacity_exceeded():
    # 総容量 5 に対して総需要 8 -> 全顧客を回れず PARTIAL
    d = np.array([[0, 2, 3], [2, 0, 2], [3, 2, 0]], dtype=float)
    vehicles = [{"id": 1, "start": 0, "end": 0, "capacity": 5}]
    jobs = [
        {"id": 1, "location": 1, "demand": 4},
        {"id": 2, "location": 2, "demand": 4},
    ]
    res = solve_vrp(d, vehicles, jobs)
    assert res["status"] == "PARTIAL"
    assert len(res["unassigned_jobs"]) == 1
    assert res["recompute"]["capacity_ok"]


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_tsp_matches_brute_force(seed):
    rng = np.random.default_rng(seed)
    pts = rng.uniform(0, 20, size=(6, 2))
    d = np.round(np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=-1), 2)
    vehicles = [{"id": 1, "start": 0, "end": 0}]
    jobs = [{"id": i, "location": i} for i in range(1, 6)]

    res = solve_vrp(d, vehicles, jobs, scale=100)
    assert res["status"] == "ALL_SERVED"

    best = min(
        sum(d[a, b] for a, b in zip((0, *perm), (*perm, 0)))
        for perm in itertools.permutations(range(1, 6))
    )
    assert res["total_duration"] == pytest.approx(best, abs=1e-6)
    assert res["total_duration"] <= res["heuristic_duration"] + 1e-6


def test_recompute_detects_capacity_and_tw_violation():
    d = np.array([[0, 10], [10, 0]], dtype=float)
    vehicles = [{"id": 1, "start": 0, "end": 0, "capacity": 5, "time_window": (0, 30)}]
    jobs = [{"id": 1, "location": 1, "demand": 6, "service": 1, "time_windows": [(0, 5)]}]
    bad_routes = [
        {
            "vehicle_id": 1,
            "steps": [
                {"type": "start", "location_index": 0, "job_id": None},
                {"type": "job", "location_index": 1, "job_id": 1},
                {"type": "end", "location_index": 0, "job_id": None},
            ],
        }
    ]
    recomp = vrp_recompute(d, bad_routes, vehicles, jobs)
    assert not recomp["capacity_ok"]
    assert not recomp["time_window_ok"]
