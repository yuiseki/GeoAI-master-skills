"""Accessibility of demand to supply: how much facility capacity each demand point can draw on, once the
capacity is shared among everyone who can reach the facility.

Two-step floating catchment (2SFCA) and its decayed forms:
    step 1  for each facility j: R_j = S_j / sum_k P_k W(c_kj)      (supply per unit of demand it serves)
    step 2  for each origin i:   A_i = sum_j R_j W(c_ij)
W is 1 within the catchment and 0 beyond it (binary), or decays inside it (linear, gaussian, steps).
With the same W in both steps, sum_i P_i A_i equals the supply of the facilities that have demand in reach:
the supply is shared out, not counted twice. A is in supply units per demand unit (beds per person).

Gravity (Hansen): A_i = sum_j S_j f(c_ij), with no sharing among competing demand (--method hansen).
Regional ratio: supply over demand inside each region of --region (--method ratio), no travel at all.

Inputs: an origins table (id, the demand column, optional region and report columns), a facilities table
(id, the supply column, optional region), and a cost table (origin, facility, cost) in any one unit
(minutes, metres). A pair absent from the cost table is unreachable. CSV or Parquet.

Each origin gets a status: served (some facility weighs > 0), no_facility_in_catchment (reachable
facilities, all beyond the catchment), unreachable (no finite cost). Each facility: allocated, or
no_demand_in_catchment (its supply reaches no demand and is reported, not spread).

--report COLUMN (true/false) keeps every origin in the competition but summarises only the true ones:
pad the study area with a ring of origins and facilities so that edge facilities see their real demand.

Usage:
    uvx --with numpy --with duckdb python accessibility.py ORIGINS FACILITIES COSTS \\
        --demand COL --supply COL --catchment 30 [--decay binary|linear|gaussian|steps|power] \\
        [--steps 10:1,20:0.6,30:0.2] [--beta 1] [--method 2sfca|hansen|ratio] [--region COL] \\
        [--report COL] [--sensitivity 15 45] --out access.csv
"""

import argparse
import math
from pathlib import Path

import numpy as np


def weight(d, kind, catchment, steps=None, beta=None):
    """Weight of a cost d (array; inf for unreachable). Zero beyond the catchment (none for power without one)."""
    d = np.asarray(d, float)
    inside = np.isfinite(d) if catchment is None else d <= catchment
    if kind == "binary":
        w = np.ones_like(d)
    elif kind == "linear":
        w = 1 - d / catchment
    elif kind == "gaussian":
        e = math.exp(-0.5)
        w = (np.exp(-0.5 * (d / catchment) ** 2) - e) / (1 - e)
    elif kind == "steps":
        w = np.zeros_like(d)
        for upper, value in sorted(steps, reverse=True):
            w[d <= upper] = value
    elif kind == "power":
        if (inside & (d <= 0)).any():
            raise SystemExit("power decay at a zero cost is infinite; floor the costs (the time to reach a "
                             "neighbouring facility) before using it")
        with np.errstate(divide="ignore"):
            w = d ** -beta
    else:
        raise SystemExit(f"unknown decay {kind}")
    return np.where(inside & np.isfinite(d), np.clip(w, 0, None), 0.0)


def fca(demand, supply, cost, w):
    """2SFCA with weight function w; cost is origins x facilities (inf = unreachable)."""
    P, S, C = np.asarray(demand, float), np.asarray(supply, float), np.asarray(cost, float)
    W = w(C)
    D = P @ W
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.where(D > 0, S / D, np.nan)
    A = W @ np.nan_to_num(R)
    finite = np.isfinite(C)
    status = np.where((W > 0).any(1), "served", np.where(finite.any(1), "no_facility_in_catchment", "unreachable"))
    nearest = np.where(finite.any(1), np.where(finite, C, np.inf).min(1), np.inf)
    return {"access": A, "ratio": R, "demand_in_catchment": D, "status": status, "nearest": nearest,
            "in_catchment": (W > 0).sum(1),
            "facility_status": np.where(D > 0, "allocated", "no_demand_in_catchment")}


def hansen(supply, cost, f):
    return np.asarray(f(np.asarray(cost, float)) @ np.asarray(supply, float))


def regional_ratio(demand, demand_region, supply, supply_region):
    out = {}
    for r in sorted(set(demand_region.tolist()) | set(supply_region.tolist())):
        p, s = demand[demand_region == r].sum(), supply[supply_region == r].sum()
        out[r] = s / p if p > 0 else float("nan")
    return out


def matrix_from_pairs(origins, facilities, pairs):
    oi = {o: i for i, o in enumerate(origins)}
    fi = {f: j for j, f in enumerate(facilities)}
    m = np.full((len(origins), len(facilities)), np.inf)
    seen, problems = set(), []
    for o, f, c in pairs:
        if o not in oi or f not in fi:
            problems.append(f"unknown pair ({o}, {f})")
        elif (o, f) in seen:
            problems.append(f"pair ({o}, {f}) appears twice")
        elif c is None or not (c >= 0) or math.isnan(c):
            problems.append(f"pair ({o}, {f}) has cost {c}")
        else:
            seen.add((o, f))
            m[oi[o], fi[f]] = c
    if problems:
        raise SystemExit(f"{len(problems)} bad rows in the cost table, e.g. {problems[:3]}")
    return m


def _read(path, cols):
    import duckdb

    q = ", ".join(f'"{c}"' for c in cols)
    return duckdb.sql(f"select {q} from '{path}'").fetchall()


def _truthy(v):
    return str(v).strip().lower() in ("true", "1", "t", "yes")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("origins")
    p.add_argument("facilities")
    p.add_argument("costs")
    p.add_argument("--demand", required=True, help="the demand column, as the question defines demand")
    p.add_argument("--supply", required=True)
    p.add_argument("--id", default="id")
    p.add_argument("--origin-col", default="origin")
    p.add_argument("--facility-col", default="facility")
    p.add_argument("--cost-col", default="cost")
    p.add_argument("--method", choices=["2sfca", "hansen", "ratio"], default="2sfca")
    p.add_argument("--catchment", type=float)
    p.add_argument("--decay", choices=["binary", "linear", "gaussian", "steps", "power"], default="binary")
    p.add_argument("--steps", help="upper:weight pairs, e.g. 10:1,20:0.6,30:0.2")
    p.add_argument("--beta", type=float)
    p.add_argument("--region")
    p.add_argument("--report")
    p.add_argument("--sensitivity", type=float, nargs="*", default=[])
    p.add_argument("--out", required=True)
    a = p.parse_args()
    if a.method == "2sfca" and a.catchment is None:
        p.error("2sfca needs --catchment (in the cost table's unit)")
    if a.decay == "steps" and not a.steps:
        p.error("--decay steps needs --steps")
    if a.decay == "power" and a.beta is None:
        p.error("--decay power needs --beta")
    steps = [tuple(map(float, s.split(":"))) for s in a.steps.split(",")] if a.steps else None

    ocols = [a.id, a.demand] + [c for c in (a.region, a.report) if c]
    orows = _read(a.origins, ocols)
    frows = _read(a.facilities, [a.id, a.supply] + ([a.region] if a.region else []))
    oid = [str(r[0]) for r in orows]
    fid = [str(r[0]) for r in frows]
    for name, ids in (("origins", oid), ("facilities", fid)):
        if len(set(ids)) != len(ids):
            raise SystemExit(f"{name} have duplicate ids")
    P = np.array([r[1] for r in orows], float)
    S = np.array([r[1] for r in frows], float)
    if not (np.isfinite(P).all() and (P >= 0).all() and np.isfinite(S).all() and (S >= 0).all()):
        raise SystemExit("demand and supply must be finite and not negative")
    report = np.array([_truthy(r[ocols.index(a.report)]) for r in orows]) if a.report else np.ones(len(oid), bool)
    unit = f"{a.supply} per {a.demand}"
    print(f"origins {len(oid)} (demand {P.sum():g}), facilities {len(fid)} (supply {S.sum():g}); "
          f"accessibility in {unit}")

    if a.method == "ratio":
        if not a.region:
            p.error("--method ratio needs --region")
        dreg = np.array([str(r[2]) for r in orows])
        sreg = np.array([str(r[2]) for r in frows])
        out = regional_ratio(P, dreg, S, sreg)
        for k, v in out.items():
            print(f"  region {k}: {v:.6g}")
        A = np.array([out[r] for r in dreg])
        _write(a.out, oid, P, A, np.full(len(oid), "region"), np.full(len(oid), np.nan), np.zeros(len(oid), int))
        return

    C = matrix_from_pairs(oid, fid, [(str(o), str(f), None if c is None else float(c))
                                     for o, f, c in _read(a.costs, [a.origin_col, a.facility_col, a.cost_col])])

    def run(catchment):
        w = lambda d: weight(d, a.decay, catchment, steps, a.beta)
        if a.method == "hansen":
            A = hansen(S, C, w)
            return {"access": A, "status": np.where(np.isfinite(C).any(1), "served", "unreachable"),
                    "nearest": np.where(np.isfinite(C), C, np.inf).min(1), "in_catchment": (w(C) > 0).sum(1)}
        return fca(P, S, C, w)

    r = run(a.catchment)
    counts = {k: int((r["status"] == k).sum()) for k in ("served", "no_facility_in_catchment", "unreachable")}
    print(f"origins {len(oid)}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if a.method == "2sfca":
        alloc = S[r["demand_in_catchment"] > 0].sum()
        total = float((P * r["access"]).sum())
        if not math.isclose(total, alloc, rel_tol=1e-9, abs_tol=1e-9):
            raise SystemExit(f"demand-weighted accessibility {total} does not add up to the allocated supply {alloc}")
        print(f"supply {S.sum():g} = allocated {alloc:g} + unallocated {S.sum() - alloc:g} "
              f"(facilities with no demand in catchment: {int((r['facility_status'] != 'allocated').sum())})")
    _summary(r["access"], P, report, f"catchment {a.catchment:g}" if a.catchment is not None else "no catchment")
    print(f"reported origins {int(report.sum())} of {len(oid)}")
    for c in a.sensitivity:
        _summary(run(c)["access"], P, report, f"catchment {c:g}")
    _write(a.out, oid, P, r["access"], r["status"], r["nearest"], r["in_catchment"])
    if a.method == "2sfca":
        fout = Path(a.out).with_suffix(".facilities" + Path(a.out).suffix)
        with open(fout, "w") as f:
            f.write("id,supply,demand_in_catchment,ratio,status\n")
            for i, j in enumerate(fid):
                f.write(f"{j},{S[i]},{r['demand_in_catchment'][i]},{r['ratio'][i]},{r['facility_status'][i]}\n")
        print(f"wrote {a.out} and {fout}")


def _summary(A, P, report, label):
    m = report
    zero = P[m][A[m] == 0].sum() / P[m].sum() if P[m].sum() else float("nan")
    q = np.quantile(A[m], [0.1, 0.5, 0.9]) if m.any() else [np.nan] * 3
    print(f"{label}: demand-weighted mean {np.average(A[m], weights=P[m]) if P[m].sum() else float('nan'):.6g}, "
          f"p10 {q[0]:.6g}, median {q[1]:.6g}, p90 {q[2]:.6g}, share of demand with 0 {zero:.3f}")


def _write(path, ids, P, A, status, nearest, n):
    with open(path, "w") as f:
        f.write("id,demand,accessibility,status,nearest_cost,facilities_in_catchment\n")
        for i, o in enumerate(ids):
            f.write(f"{o},{P[i]},{A[i]},{status[i]},{nearest[i]},{n[i]}\n")


if __name__ == "__main__":
    main()
