"""VROOM (pyvroom) による配車・巡回ルート最適化 (CVRP / VRPTW) と自己検証。

pyvroom で容量制約・時間枠制約付きの複数車両ルート問題 (CVRP / VRPTW) を解き、
返されたルート列から元の浮動小数点行列・容量・時間枠で目的値と制約違反を直接再計算する。
また単純な最近傍ヒューリスティックをベースラインとして併記する。
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np
import vroom


def _to_vroom_matrix(arr: np.ndarray) -> vroom._vroom.Matrix:
    """Windows / Linux 双方で pybind11 バッファ形式エラーを避けて Matrix を構築する。"""
    return vroom._vroom.Matrix(np.asarray(arr, dtype=np.uintc))


def vrp_recompute(
    duration_matrix: np.ndarray,
    routes: list[dict[str, Any]],
    vehicles: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    cost_matrix: np.ndarray | None = None,
) -> dict[str, Any]:
    """返されたルートから総移動時間・総コスト・制約充足を元の値で直接再計算する。"""
    d_mat = np.asarray(duration_matrix, dtype=float)
    c_mat = d_mat if cost_matrix is None else np.asarray(cost_matrix, dtype=float)

    veh_by_id = {int(v["id"]): v for v in vehicles}
    job_by_id = {int(j["id"]): j for j in jobs}

    total_duration = 0.0
    total_cost = 0.0
    served_jobs: list[int] = []
    capacity_ok = True
    time_window_ok = True

    for route in routes:
        vid = int(route["vehicle_id"])
        veh = veh_by_id[vid]
        steps = route["steps"]
        if not steps:
            continue

        load = 0
        current_time = 0.0
        v_tw = veh.get("time_window")
        if v_tw is not None:
            current_time = float(v_tw[0])

        prev_loc = int(steps[0]["location_index"])
        for step in steps[1:]:
            curr_loc = int(step["location_index"])
            travel = float(d_mat[prev_loc, curr_loc])
            total_duration += travel
            total_cost += float(c_mat[prev_loc, curr_loc])
            current_time += travel

            if step["type"] == "job":
                jid = int(step["job_id"])
                served_jobs.append(jid)
                job = job_by_id[jid]
                load += int(job.get("demand", 0))

                tws = job.get("time_windows")
                if tws:
                    # 少なくとも 1 つの時間枠内にサービス開始時刻が収まるか確認
                    matched = False
                    best_start = current_time
                    for tw_s, tw_e in tws:
                        start_t = max(current_time, float(tw_s))
                        if start_t <= float(tw_e) + 1e-6:
                            matched = True
                            best_start = start_t
                            break
                    if not matched:
                        time_window_ok = False
                    else:
                        current_time = best_start
                current_time += float(job.get("service", 0.0))

            prev_loc = curr_loc

        if v_tw is not None and current_time > float(v_tw[1]) + 1e-6:
            time_window_ok = False
        v_cap = veh.get("capacity")
        if v_cap is not None and load > int(v_cap):
            capacity_ok = False

    served_set = set(served_jobs)
    unassigned = [int(j["id"]) for j in jobs if int(j["id"]) not in served_set]
    all_jobs_served = len(unassigned) == 0 and len(served_jobs) == len(jobs)

    return {
        "total_duration": float(total_duration),
        "total_cost": float(total_cost),
        "capacity_ok": bool(capacity_ok),
        "time_window_ok": bool(time_window_ok),
        "all_jobs_served": bool(all_jobs_served),
        "unassigned_jobs": unassigned,
    }


def vrp_nearest_neighbor_heuristic(
    duration_matrix: np.ndarray,
    vehicles: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    """単純な最近傍挿入ヒューリスティック (ベースライン比較用)。"""
    d_mat = np.asarray(duration_matrix, dtype=float)
    remaining = {int(j["id"]): j for j in jobs}
    routes: list[dict[str, Any]] = []
    total_duration = 0.0

    for veh in vehicles:
        vid = int(veh["id"])
        start_loc = int(veh.get("start", 0))
        end_loc = int(veh.get("end", start_loc))
        cap = veh.get("capacity")
        v_tw = veh.get("time_window")

        curr_loc = start_loc
        curr_time = float(v_tw[0]) if v_tw is not None else 0.0
        load = 0
        steps: list[dict[str, Any]] = [
            {"type": "start", "location_index": start_loc, "job_id": None}
        ]

        while remaining:
            best_jid = None
            best_travel = float("inf")
            best_start_time = curr_time

            for jid, job in remaining.items():
                demand = int(job.get("demand", 0))
                if cap is not None and load + demand > int(cap):
                    continue
                j_loc = int(job["location"])
                travel = float(d_mat[curr_loc, j_loc])
                arr_t = curr_time + travel
                service = float(job.get("service", 0.0))
                tws = job.get("time_windows")

                start_t = arr_t
                if tws:
                    feasible_tw = False
                    for tw_s, tw_e in tws:
                        cand_start = max(arr_t, float(tw_s))
                        if cand_start <= float(tw_e) + 1e-9:
                            start_t = cand_start
                            feasible_tw = True
                            break
                    if not feasible_tw:
                        continue

                back_travel = float(d_mat[j_loc, end_loc])
                if v_tw is not None and start_t + service + back_travel > float(v_tw[1]) + 1e-9:
                    continue

                if travel < best_travel:
                    best_travel = travel
                    best_jid = jid
                    best_start_time = start_t

            if best_jid is None:
                break

            job = remaining.pop(best_jid)
            j_loc = int(job["location"])
            total_duration += best_travel
            load += int(job.get("demand", 0))
            curr_time = best_start_time + float(job.get("service", 0.0))
            curr_loc = j_loc
            steps.append(
                {
                    "type": "job",
                    "location_index": j_loc,
                    "job_id": int(best_jid),
                    "arrival": float(best_start_time),
                }
            )

        if len(steps) > 1:
            total_duration += float(d_mat[curr_loc, end_loc])
            steps.append(
                {
                    "type": "end",
                    "location_index": end_loc,
                    "job_id": None,
                    "arrival": float(curr_time + d_mat[curr_loc, end_loc]),
                }
            )
            routes.append({"vehicle_id": vid, "steps": steps})

    return {
        "routes": routes,
        "total_duration": float(total_duration),
        "unassigned_jobs": sorted(remaining.keys()),
    }


def solve_vrp(
    duration_matrix: np.ndarray,
    vehicles: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    cost_matrix: np.ndarray | None = None,
    scale: int = 100,
    exploration_level: int = 5,
    nb_threads: int = 1,
) -> dict[str, Any]:
    """pyvroom を使って CVRP / VRPTW を解き、再計算とベースライン比較を返す。"""
    d_mat = np.asarray(duration_matrix, dtype=float)
    d_int = np.rint(d_mat * scale).astype(np.uintc)

    prob = vroom.Input()
    prob.set_durations_matrix(profile="car", matrix_input=_to_vroom_matrix(d_int))

    if cost_matrix is not None:
        c_mat = np.asarray(cost_matrix, dtype=float)
        c_int = np.rint(c_mat * scale).astype(np.uintc)
        prob.set_costs_matrix(profile="car", matrix_input=_to_vroom_matrix(c_int))

    vroom_vehicles = []
    for v in vehicles:
        kwargs: dict[str, Any] = {
            "id": int(v["id"]),
            "start": int(v.get("start", 0)),
            "end": int(v.get("end", v.get("start", 0))),
            "profile": "car",
        }
        if v.get("capacity") is not None:
            kwargs["capacity"] = [int(v["capacity"])]
        if v.get("time_window") is not None:
            tw_s, tw_e = v["time_window"]
            kwargs["time_window"] = vroom.TimeWindow(
                int(round(float(tw_s) * scale)),
                int(round(float(tw_e) * scale)),
            )
        vroom_vehicles.append(vroom.Vehicle(**kwargs))
    prob.add_vehicle(vroom_vehicles)

    vroom_jobs = []
    for j in jobs:
        kwargs = {
            "id": int(j["id"]),
            "location": int(j["location"]),
            "default_service": int(round(float(j.get("service", 0.0)) * scale)),
        }
        if j.get("demand") is not None and int(j["demand"]) > 0:
            kwargs["delivery"] = [int(j["demand"])]
        if j.get("time_windows"):
            kwargs["time_windows"] = [
                vroom.TimeWindow(
                    int(round(float(tw_s) * scale)),
                    int(round(float(tw_e) * scale)),
                )
                for tw_s, tw_e in j["time_windows"]
            ]
        vroom_jobs.append(vroom.Job(**kwargs))
    prob.add_job(vroom_jobs)

    sol = prob.solve(exploration_level=exploration_level, nb_threads=nb_threads)

    routes: list[dict[str, Any]] = []
    if len(sol.routes) > 0:
        for vid, group in sol.routes.groupby("vehicle_id", sort=False):
            steps = []
            for _, row in group.iterrows():
                step_type = str(row["type"])
                job_id = None if step_type in ("start", "end") else int(row["id"])
                steps.append(
                    {
                        "type": step_type,
                        "location_index": int(row["location_index"]),
                        "job_id": job_id,
                        "arrival": float(row["arrival"]) / scale,
                        "waiting_time": float(row["waiting_time"]) / scale,
                        "service": float(row["service"]) / scale,
                    }
                )
            routes.append({"vehicle_id": int(vid), "steps": steps})

    recomp = vrp_recompute(
        duration_matrix=d_mat,
        routes=routes,
        vehicles=vehicles,
        jobs=jobs,
        cost_matrix=cost_matrix,
    )
    heur = vrp_nearest_neighbor_heuristic(
        duration_matrix=d_mat,
        vehicles=vehicles,
        jobs=jobs,
    )

    unassigned = recomp["unassigned_jobs"]
    return {
        "status": "ALL_SERVED" if len(unassigned) == 0 else "PARTIAL",
        "total_duration": recomp["total_duration"],
        "total_cost": recomp["total_cost"],
        "heuristic_duration": heur["total_duration"],
        "heuristic_unassigned": heur["unassigned_jobs"],
        "unassigned_jobs": unassigned,
        "routes": routes,
        "recompute": recomp,
    }


def _read_table(path: str) -> list[dict[str, Any]]:
    import duckdb

    con = duckdb.connect()
    if path.lower().endswith(".parquet"):
        rel = con.read_parquet(path)
    else:
        rel = con.read_csv(path)
    cols = rel.columns
    rows = rel.fetchall()
    return [dict(zip(cols, r)) for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="VROOM (pyvroom) VRP 最適化")
    parser.add_argument("--matrix", required=True, help="OD 行列 (origin, destination, duration)")
    parser.add_argument("--jobs", required=True, help="顧客・タスク表 (id, location, demand, service, tw_start, tw_end)")
    parser.add_argument("--vehicles", required=True, help="車両表 (id, start, end, capacity, tw_start, tw_end)")
    parser.add_argument("--scale", type=int, default=100, help="整数スケーリング倍率")
    parser.add_argument("--exploration", type=int, default=5, help="VROOM exploration_level (1..5)")
    args = parser.parse_args()

    od_rows = _read_table(args.matrix)
    max_idx = max(max(int(r["origin"]), int(r["destination"])) for r in od_rows)
    n = max_idx + 1
    d_mat = np.zeros((n, n), dtype=float)
    for r in od_rows:
        d_mat[int(r["origin"]), int(r["destination"])] = float(r["duration"])

    job_rows = _read_table(args.jobs)
    jobs = []
    for r in job_rows:
        j: dict[str, Any] = {
            "id": int(r["id"]),
            "location": int(r["location"]),
            "demand": int(r.get("demand") or 0),
            "service": float(r.get("service") or 0.0),
        }
        if r.get("tw_start") is not None and r.get("tw_end") is not None:
            j["time_windows"] = [(float(r["tw_start"]), float(r["tw_end"]))]
        jobs.append(j)

    veh_rows = _read_table(args.vehicles)
    vehicles = []
    for r in veh_rows:
        v: dict[str, Any] = {
            "id": int(r["id"]),
            "start": int(r.get("start") or 0),
            "end": int(r.get("end") or 0),
        }
        if r.get("capacity") is not None:
            v["capacity"] = int(r["capacity"])
        if r.get("tw_start") is not None and r.get("tw_end") is not None:
            v["time_window"] = (float(r["tw_start"]), float(r["tw_end"]))
        vehicles.append(v)

    res = solve_vrp(
        duration_matrix=d_mat,
        vehicles=vehicles,
        jobs=jobs,
        scale=args.scale,
        exploration_level=args.exploration,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
