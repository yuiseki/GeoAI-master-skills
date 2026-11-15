"""uvx --with numpy --with pyvroom --with ortools --with pytest pytest test_vrp_crosscheck.py"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from cpsat_location import solve_schedule
from vrp_routing import solve_vrp


@pytest.mark.parametrize("seed", [10, 11, 12, 13, 14])
def test_vrp_matches_cpsat_schedule_on_small_vrptw(seed):
    rng = np.random.default_rng(seed)
    n_nodes = 5  # 0 はデポ、1..4 はタスク
    pts = rng.uniform(0, 15, size=(n_nodes, 2))
    d = np.rint(np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=-1)).astype(int)

    tasks = []
    jobs = []
    for i in range(1, n_nodes):
        tw_s = int(rng.integers(0, 20))
        tw_e = tw_s + int(rng.integers(25, 45))
        svc = int(rng.integers(1, 4))
        tasks.append({"id": i, "start_min": tw_s, "end_max": tw_e, "duration": svc})
        jobs.append({"id": i, "location": i, "service": svc, "time_windows": [(tw_s, tw_e)]})

    vehicles = [
        {"id": 1, "start": 0, "end": 0, "time_window": (0, 200)},
        {"id": 2, "start": 0, "end": 0, "time_window": (0, 200)},
    ]

    cp_res = solve_schedule(tasks=tasks, travel_matrix=d, num_teams=2)
    vrp_res = solve_vrp(duration_matrix=d, vehicles=vehicles, jobs=jobs, scale=100)

    assert cp_res["status"] == "optimal"
    assert vrp_res["status"] == "ALL_SERVED"
    assert vrp_res["recompute"]["time_window_ok"]
    assert vrp_res["total_duration"] == pytest.approx(cp_res["total_travel"], abs=0.05)
