"""Solve capacitated single-source facility location and time-windowed scheduling with OR-Tools CP-SAT.

Problems:
    cflp        Capacitated single-source facility location: open at most p sites (optionally with
                fixed opening costs) and assign each demand point wholly to one open site within
                its capacity, minimising weighted distance + opening cost.
    schedule    Team/vehicle shift scheduling across locations with time windows, service
                durations, and optional travel times between consecutive tasks (AddNoOverlap /
                AddCircuit), minimising total travel + waiting/makespan.

CP-SAT requires integer coefficients. Real-valued costs/weights are scaled by `scale` (default 100)
and rounded to integers. After solving, the script recomputes the objective and checks every
constraint (capacity, single assignment, time windows, non-overlap) on the unscaled inputs; if
anything disagrees or a feasible heuristic beats the solver, it exits with an error. For cflp it also reports a lower
bound in the original units and the gap to it (rounding_slack, bound_report), so a run stopped by the time limit says
how far from optimal it may be; when weights or capacities are not multiples of 1/scale, no bound is claimed for the
original problem.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with ortools python cpsat_location.py \
        --problem cflp MATRIX DEMAND FACILITIES --p 3 --demand COL --capacity COL [--out assign.csv]
"""

import argparse
import time

import numpy as np
from ortools.sat.python import cp_model


def _to_int_array(arr, scale=1):
    scaled = np.rint(np.asarray(arr, dtype=float) * scale)
    return scaled.astype(np.int64)


def cflp_recompute(d, w, s, open_sites, assign, fixed_cost=None):
    """Recompute unscaled objective and validate every CFLP constraint."""
    d = np.asarray(d, dtype=float)
    w = np.asarray(w, dtype=float)
    s = np.asarray(s, dtype=float)
    n, m = d.shape
    open_set = set(int(j) for j in open_sites)
    if len(assign) != n:
        raise ValueError("assignment length mismatch")
    loads = np.zeros(m, dtype=float)
    total_dist = 0.0
    for i in range(n):
        j = int(assign[i])
        if j not in open_set:
            raise ValueError(f"demand {i} assigned to closed site {j}")
        if not np.isfinite(d[i, j]):
            raise ValueError(f"demand {i} assigned to unreachable site {j}")
        loads[j] += w[i]
        total_dist += w[i] * d[i, j]
    for j in open_set:
        if loads[j] > s[j] + 1e-6:
            raise ValueError(f"site {j} load {loads[j]} exceeds capacity {s[j]}")
    fc = 0.0
    if fixed_cost is not None:
        fc_arr = np.asarray(fixed_cost, dtype=float)
        fc = float(sum(fc_arr[j] for j in open_set))
    return float(total_dist + fc), loads


def cflp_heuristic(d, w, s, p, fixed_cost=None):
    """Greedy heuristic for capacitated single-source facility location."""
    d = np.asarray(d, dtype=float)
    w = np.asarray(w, dtype=float)
    s = np.asarray(s, dtype=float)
    n, m = d.shape
    if fixed_cost is None:
        fixed_cost = np.zeros(m, dtype=float)
    else:
        fixed_cost = np.asarray(fixed_cost, dtype=float)

    # Try greedy site addition based on nearest feasible assignment
    chosen = []
    best_overall = None

    def try_assign(open_list):
        if not open_list:
            return None
        rem = s[open_list].copy()
        assign = [-1] * n
        # Sort demands descending by weight so large indivisible demands get placed first
        order = np.argsort(-w)
        for i in order:
            # Nearest open site with enough remaining capacity
            best_k = None
            best_dist = np.inf
            for k_idx, j in enumerate(open_list):
                if rem[k_idx] + 1e-9 >= w[i] and d[i, j] < best_dist:
                    best_dist = d[i, j]
                    best_k = k_idx
            if best_k is None:
                return None
            assign[i] = open_list[best_k]
            rem[best_k] -= w[i]
        val, _ = cflp_recompute(d, w, s, open_list, assign, fixed_cost)
        return val, assign

    for _ in range(min(p, m)):
        cand_best = None
        for j in range(m):
            if j in chosen:
                continue
            trial = chosen + [j]
            res = try_assign(trial)
            if res is not None:
                val, assign = res
                if cand_best is None or val < cand_best[0]:
                    cand_best = (val, j, assign)
        if cand_best is not None:
            chosen.append(cand_best[1])
            best_overall = (cand_best[0], list(chosen), cand_best[2])
        else:
            # If still infeasible with current count, add site with largest capacity
            rem_cands = [j for j in range(m) if j not in chosen]
            if not rem_cands:
                break
            chosen.append(max(rem_cands, key=lambda j: s[j]))
            res = try_assign(chosen)
            if res is not None:
                best_overall = (res[0], list(chosen), res[1])

    if best_overall is None:
        return None
    return {"open": best_overall[1], "assign": best_overall[2], "recomputed": best_overall[0]}


def rounding_slack(cost, fixed_cost, p, scale):
    """The most the rounded objective can rise above the original one for any solution, in original units.

    CP-SAT minimises rint(c * scale) / scale instead of c, so its bound B holds for the rounded costs. For any
    solution, original >= rounded - (what rounding added to the terms it uses) >= B - slack. A solution uses one
    assignment per demand and at most p opening costs, so the slack is, per demand, the largest amount rounding added
    over the sites it can use, plus the p largest added to opening costs. Exact multiples of 1 / scale add nothing."""
    def added(c):
        a = np.asarray(c, dtype=float) * scale
        return np.maximum(np.rint(a) - a, 0.0) / scale
    per_demand = np.where(np.isfinite(cost), added(np.where(np.isfinite(cost), cost, 0.0)), 0.0).max(axis=1)
    fc = np.sort(added(fixed_cost))[::-1][:p]
    return float(per_demand.sum() + fc.sum())


def bound_report(scaled_bound, recomputed, slack, scale, exact_capacity):
    """The solver's lower bound in the original units, and what it is a bound for.

    scaled_bound / scale - slack (rounding_slack) bounds the original objective, provided the rounded model accepts
    every original solution. That holds when weights and capacities are exact multiples of 1 / scale (the capacity rows
    are then the same); otherwise the bound is only for the rounded model and no gap to the original optimum is claimed.
    """
    r = {"rounded_model_bound": scaled_bound / scale, "rounding_slack": slack}
    if not exact_capacity:
        r.update(bound=None, gap=None, bound_scope="rounded_model")
        return r
    bound = scaled_bound / scale - slack
    r.update(bound=bound, bound_scope="original",
             gap=(recomputed - bound) / max(abs(recomputed), 1e-12))
    return r


def _exact(arr, scale):
    a = np.asarray(arr, dtype=float) * scale
    return bool(np.all(np.abs(a - np.rint(a)) <= 1e-9 * np.maximum(1.0, np.abs(a))))


def solve_cflp(d, w, s, p, fixed_cost=None, scale=100, time_limit_s=30.0, workers=None):
    """Solve capacitated single-source facility location using OR-Tools CP-SAT.

    status "optimal" is CP-SAT's proof for the rounded model. The result also gives a lower bound in the original
    units (bound_report), so a run stopped by the time limit ("feasible") says how far from optimal it may be."""
    d = np.asarray(d, dtype=float)
    w = np.asarray(w, dtype=float)
    s = np.asarray(s, dtype=float)
    n, m = d.shape
    if p < 1 or p > m:
        raise SystemExit(f"p={p} must be between 1 and {m}")
    for i in range(n):
        if not np.any(np.isfinite(d[i, :])):
            raise SystemExit(f"demand {i} cannot reach any facility")
        if w[i] > s.max() + 1e-9:
            raise SystemExit(f"demand {i} weight {w[i]} exceeds max facility capacity {s.max()}")

    if fixed_cost is None:
        fc = np.zeros(m, dtype=float)
    else:
        fc = np.asarray(fixed_cost, dtype=float)

    w_int = _to_int_array(w, scale=scale)
    s_int = np.floor(s * scale + 1e-9).astype(np.int64)
    fc_int = _to_int_array(fc, scale=scale)

    model = cp_model.CpModel()
    y = [model.NewBoolVar(f"y_{j}") for j in range(m)]
    x = {}
    for i in range(n):
        for j in range(m):
            if np.isfinite(d[i, j]) and w_int[i] <= s_int[j]:
                x[(i, j)] = model.NewBoolVar(f"x_{i}_{j}")
                model.Add(x[(i, j)] <= y[j])

    model.Add(sum(y) <= p)
    for i in range(n):
        avail = [x[(i, j)] for j in range(m) if (i, j) in x]
        if not avail:
            raise SystemExit(f"demand {i} has no reachable facility with enough capacity")
        model.AddExactlyOne(avail)

    for j in range(m):
        terms = [int(w_int[i]) * x[(i, j)] for i in range(n) if (i, j) in x]
        if terms:
            model.Add(sum(terms) <= int(s_int[j]) * y[j])

    obj_terms = []
    for (i, j), var in x.items():
        coeff = int(np.rint(w[i] * d[i, j] * scale))
        if coeff != 0:
            obj_terms.append(coeff * var)
    for j in range(m):
        if fc_int[j] != 0:
            obj_terms.append(int(fc_int[j]) * y[j])
    model.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    if workers:
        solver.parameters.num_search_workers = int(workers)
    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        hint = " (no proof of infeasibility: the time limit ran out first)" if status == cp_model.UNKNOWN else ""
        raise SystemExit(f"CP-SAT CFLP failed with status {solver.StatusName(status)}{hint}")

    open_sites = [j for j in range(m) if solver.Value(y[j]) == 1]
    assign = []
    for i in range(n):
        assigned_j = [j for j in range(m) if (i, j) in x and solver.Value(x[(i, j)]) == 1]
        if len(assigned_j) != 1:
            raise SystemExit(f"invalid assignment for demand {i}: {assigned_j}")
        assign.append(assigned_j[0])

    recomputed, loads = cflp_recompute(d, w, s, open_sites, assign, fc)
    heur = cflp_heuristic(d, w, s, p, fc)
    usable = np.full(d.shape, np.inf)
    for (i, j) in x:
        usable[i, j] = w[i] * d[i, j]
    slack = rounding_slack(usable, fc, p, scale)
    bnd = bound_report(solver.BestObjectiveBound(), recomputed, slack, scale, _exact(w, scale) and _exact(s, scale))
    if bnd["bound"] is not None:
        # Any solution feasible for the original problem is at least the bound; one below it means a wrong model.
        for name, val in (("CP-SAT", recomputed), ("heuristic", heur["recomputed"] if heur else None)):
            if val is not None and val < bnd["bound"] - 1e-9 * max(1.0, abs(val)):
                raise SystemExit(f"{name} solution {val:.6g} is below the lower bound {bnd['bound']:.6g}: wrong model")
    if status == cp_model.OPTIMAL and heur is not None:
        # Allow tiny rounding tolerance from integer scaling
        tol = max(1e-4, n * 1.0 / scale)
        if recomputed > heur["recomputed"] + tol:
            raise SystemExit(
                f"CP-SAT optimal ({recomputed:.4f}) is worse than heuristic ({heur['recomputed']:.4f}): wrong model or scale too coarse"
            )

    return {
        "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
        "open": open_sites,
        "assign": assign,
        "loads": loads.tolist(),
        "recomputed": recomputed,
        "solver_objective": solver.ObjectiveValue() / scale,
        "heuristic": heur,
        "elapsed_s": round(elapsed, 4),
        **bnd,
    }


def solve_schedule(tasks, travel_matrix, num_teams, time_limit_s=30.0):
    """Schedule location-based tasks across teams with time windows and travel times.

    tasks: list of dicts with keys {id, start_min, end_max, duration} (integers, e.g. minutes)
    travel_matrix: 2D array of shape (len(tasks)+1, len(tasks)+1) where index 0 is depot,
                   and index i+1 is task i (integers, e.g. minutes).
    num_teams: integer number of available teams.
    """
    n = len(tasks)
    if n == 0:
        return {"status": "optimal", "routes": [], "makespan": 0, "total_travel": 0}
    T = np.asarray(travel_matrix, dtype=np.int64)
    if T.shape != (n + 1, n + 1):
        raise ValueError(f"travel_matrix must have shape ({n + 1}, {n + 1}), got {T.shape}")
    if num_teams < 1:
        raise ValueError("num_teams must be >= 1")

    max_horizon = max(int(t["end_max"]) + int(t["duration"]) for t in tasks) + int(T.max()) * 2

    model = cp_model.CpModel()
    start_vars = []
    end_vars = []
    # Team assignment per task: 0 .. num_teams-1
    team_vars = [model.NewIntVar(0, num_teams - 1, f"team_{i}") for i in range(n)]
    for i, t in enumerate(tasks):
        s_var = model.NewIntVar(int(t["start_min"]), int(t["end_max"]), f"start_{i}")
        e_var = model.NewIntVar(
            int(t["start_min"]) + int(t["duration"]),
            int(t["end_max"]) + int(t["duration"]),
            f"end_{i}",
        )
        model.Add(e_var == s_var + int(t["duration"]))
        start_vars.append(s_var)
        end_vars.append(e_var)

    # For each team, build optional intervals and a circuit with travel times
    total_travel_terms = []
    for k in range(num_teams):
        # Node 0 is depot, nodes 1..n are tasks
        arcs = []
        active = []
        for i in range(n):
            b = model.NewBoolVar(f"team_{k}_does_{i}")
            model.Add(team_vars[i] == k).OnlyEnforceIf(b)
            model.Add(team_vars[i] != k).OnlyEnforceIf(b.Not())
            active.append(b)
            # Self-loop when task i is not handled by team k
            arcs.append((i + 1, i + 1, b.Not()))

            # Depot -> task i
            d_to_i = model.NewBoolVar(f"arc_{k}_0_{i+1}")
            arcs.append((0, i + 1, d_to_i))
            model.Add(start_vars[i] >= int(T[0, i + 1])).OnlyEnforceIf(d_to_i)
            total_travel_terms.append(int(T[0, i + 1]) * d_to_i)

            # Task i -> depot
            i_to_d = model.NewBoolVar(f"arc_{k}_{i+1}_0")
            arcs.append((i + 1, 0, i_to_d))
            total_travel_terms.append(int(T[i + 1, 0]) * i_to_d)

        # Idle depot loop if team k does nothing
        idle = model.NewBoolVar(f"arc_{k}_0_0")
        arcs.append((0, 0, idle))
        for i in range(n):
            model.AddImplication(idle, active[i].Not())

        # Task i -> Task j
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                arc = model.NewBoolVar(f"arc_{k}_{i+1}_{j+1}")
                arcs.append((i + 1, j + 1, arc))
                model.Add(start_vars[j] >= end_vars[i] + int(T[i + 1, j + 1])).OnlyEnforceIf(arc)
                total_travel_terms.append(int(T[i + 1, j + 1]) * arc)

        model.AddCircuit(arcs)

        # Also add NoOverlap on optional intervals for stronger propagation
        opt_intervals = []
        for i in range(n):
            iv = model.NewOptionalIntervalVar(
                start_vars[i], int(tasks[i]["duration"]), end_vars[i], active[i], f"iv_{k}_{i}"
            )
            opt_intervals.append(iv)
        model.AddNoOverlap(opt_intervals)

    makespan = model.NewIntVar(0, max_horizon, "makespan")
    model.AddMaxEquality(makespan, end_vars)

    # Primary objective: total travel time; small tie-breaker on makespan
    total_travel = sum(total_travel_terms)
    model.Minimize(total_travel * 1000 + makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SystemExit(f"CP-SAT schedule failed with status {solver.StatusName(status)}")

    # Extract routes & verify manually
    routes = []
    recomputed_travel = 0
    seen_tasks = set()
    for k in range(num_teams):
        team_tasks = [i for i in range(n) if solver.Value(team_vars[i]) == k]
        team_tasks.sort(key=lambda idx: solver.Value(start_vars[idx]))
        route = []
        prev_node = 0
        prev_end = 0
        for idx in team_tasks:
            st = solver.Value(start_vars[idx])
            en = solver.Value(end_vars[idx])
            t_min = int(tasks[idx]["start_min"])
            t_max = int(tasks[idx]["end_max"])
            dur = int(tasks[idx]["duration"])
            if not (t_min <= st <= t_max):
                raise SystemExit(f"task {idx} start {st} outside window [{t_min}, {t_max}]")
            if en != st + dur:
                raise SystemExit(f"task {idx} end {en} != start {st} + dur {dur}")
            travel = int(T[prev_node, idx + 1])
            if st < prev_end + travel:
                raise SystemExit(f"task {idx} start {st} violates travel from {prev_node}: {prev_end}+{travel}")
            recomputed_travel += travel
            prev_node = idx + 1
            prev_end = en
            seen_tasks.add(idx)
            route.append({"task_index": idx, "id": tasks[idx]["id"], "start": st, "end": en})
        if team_tasks:
            recomputed_travel += int(T[prev_node, 0])
        routes.append({"team": k, "stops": route})

    if len(seen_tasks) != n:
        raise SystemExit(f"expected {n} tasks scheduled, got {len(seen_tasks)}")

    return {
        "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
        "routes": routes,
        "total_travel": recomputed_travel,
        "makespan": max((s["end"] for r in routes for s in r["stops"]), default=0),
    }


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--problem", choices=["cflp"], default="cflp")
    p.add_argument("matrix", help="Parquet/CSV with origin, destination, cost/distance")
    p.add_argument("demand", help="Parquet/CSV with id and demand column")
    p.add_argument("facilities", help="Parquet/CSV with id and capacity column")
    p.add_argument("--p", type=int, required=True, help="Max facilities to open")
    p.add_argument("--demand-col", default="demand")
    p.add_argument("--capacity-col", default="capacity")
    p.add_argument("--fixed-cost-col", default=None)
    p.add_argument("--origin-col", default="origin")
    p.add_argument("--facility-col", default="facility")
    p.add_argument("--cost-col", default="cost")
    p.add_argument("--id-col", default="id")
    p.add_argument("--scale", type=int, default=100)
    p.add_argument("--time-limit", type=float, default=30.0)
    p.add_argument("--out", help="Optional CSV path for demand-to-facility assignments")
    a = p.parse_args()

    dem_rows = duckdb.sql(f'select "{a.id_col}", "{a.demand_col}" from \'{a.demand}\'').fetchall()
    if a.fixed_cost_col:
        fac_rows = duckdb.sql(
            f'select "{a.id_col}", "{a.capacity_col}", "{a.fixed_cost_col}" from \'{a.facilities}\''
        ).fetchall()
    else:
        fac_rows = duckdb.sql(f'select "{a.id_col}", "{a.capacity_col}", 0.0 from \'{a.facilities}\'').fetchall()

    oi = {str(r[0]): i for i, r in enumerate(dem_rows)}
    fi = {str(r[0]): j for j, r in enumerate(fac_rows)}
    C = np.full((len(dem_rows), len(fac_rows)), np.inf)
    pairs = duckdb.sql(f'select "{a.origin_col}", "{a.facility_col}", "{a.cost_col}" from \'{a.matrix}\'').fetchall()
    for oo, ff, c in pairs:
        if str(oo) in oi and str(ff) in fi and c is not None:
            C[oi[str(oo)], fi[str(ff)]] = c

    w = np.array([r[1] for r in dem_rows], dtype=float)
    s = np.array([r[1] for r in fac_rows], dtype=float)
    fc = np.array([r[2] for r in fac_rows], dtype=float) if a.fixed_cost_col else None

    res = solve_cflp(C, w, s, a.p, fixed_cost=fc, scale=a.scale, time_limit_s=a.time_limit)
    open_ids = [str(fac_rows[j][0]) for j in res["open"]]
    print(f"status={res['status']} p<={a.p} open={len(open_ids)} ({open_ids}) "
          f"objective={res['recomputed']:.4f} elapsed={res['elapsed_s']}s")
    if res["bound"] is not None:
        print(f"lower_bound={res['bound']:.4f} gap={res['gap']:.4%} (original units, rounding slack "
              f"{res['rounding_slack']:.4g})")
    else:
        print(f"lower_bound=none for the original problem (weights or capacities are not multiples of 1/scale); "
              f"rounded-model bound {res['rounded_model_bound']:.4f}")
    if res["heuristic"] is not None:
        print(f"heuristic={res['heuristic']['recomputed']:.4f}")

    if a.out:
        import csv
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow([a.origin_col, a.facility_col, "demand", "cost"])
            for i, j in enumerate(res["assign"]):
                wr.writerow([dem_rows[i][0], fac_rows[j][0], w[i], C[i, j]])


if __name__ == "__main__":
    main()
