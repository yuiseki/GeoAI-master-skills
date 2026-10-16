"""Assign demand to facilities with capacities at the least total cost (the transportation problem), and read
the dual prices: what one more unit of a facility's capacity is worth, and what serving one more unit of
demand at each origin costs.

    minimise sum_ij c_ij x_ij   subject to   sum_j x_ij = d_i (every origin's demand is served)
                                             sum_i x_ij <= s_j (no facility over its capacity), x >= 0

Solved as a linear programme (scipy.optimize.linprog, HiGHS). With integer demands and capacities the flows
come out integer (the constraint matrix is totally unimodular): no rounding is needed. The duals are HiGHS's
marginals:
    capacity price  -dual of facility j's capacity row (>= 0): the drop in total cost if s_j grew by one unit.
                    0 for a facility with spare capacity
    origin price    dual of origin i's demand row: the rise in total cost if d_i grew by one unit
They satisfy complementary slackness: on every used pair, origin price - capacity price = c_ij; on every pair,
c_ij - origin price + capacity price >= 0. The script checks both, and stops if they fail.

Unreachable pairs (no cost) are not allowed. If capacity is short (sum s < sum d), the problem has no answer and
the run stops; give a dummy facility with a high cost to see who goes unserved.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python transport.py COSTS ORIGINS FACILITIES \\
        --demand COL --capacity COL [--origin-col origin --facility-col facility --cost-col cost] [--out flows.csv]
"""

import argparse

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


def solve(cost, demand, capacity):
    C = np.asarray(cost, float)
    d, s = np.asarray(demand, float), np.asarray(capacity, float)
    n, m = C.shape
    if not np.isfinite(C).all():
        raise SystemExit("some origin-facility pairs have no cost; give every pair a cost (a large one if needed)")
    if s.sum() < d.sum() - 1e-9:
        raise SystemExit(f"capacity {s.sum():g} is short of demand {d.sum():g}: no assignment serves everyone")
    rows = np.repeat(np.arange(n), m)
    cols = np.arange(n * m)
    A_eq = coo_matrix((np.ones(n * m), (rows, cols)), shape=(n, n * m))
    A_ub = coo_matrix((np.ones(n * m), (np.tile(np.arange(m), n), cols)), shape=(m, n * m))
    res = linprog(C.ravel(), A_ub=A_ub, b_ub=s, A_eq=A_eq, b_eq=d, bounds=(0, None), method="highs")
    if res.status != 0:
        raise SystemExit(f"linprog: {res.message}")
    x = res.x.reshape(n, m)
    u = res.eqlin.marginals  # origin prices
    cap_price = -res.ineqlin.marginals  # >= 0
    reduced = C - u[:, None] + cap_price[None, :]
    used = x > 1e-9
    slack_ok = bool(np.all(np.abs(reduced[used]) < 1e-7) and np.all(reduced > -1e-7))
    if not slack_ok:
        raise SystemExit("the duals do not satisfy complementary slackness: the solution is not to be trusted")
    return {"flows": x, "cost": float(res.fun), "origin_price": u, "capacity_price": cap_price,
            "spare": s - x.sum(0), "reduced_cost": reduced}


def nearest_cost(cost, demand):
    """Total cost if every origin went to its cheapest facility, ignoring capacity."""
    C = np.asarray(cost, float)
    return float((np.asarray(demand, float) * C.min(1)).sum())


def main():
    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("costs")
    p.add_argument("origins")
    p.add_argument("facilities")
    p.add_argument("--demand", required=True)
    p.add_argument("--capacity", required=True)
    p.add_argument("--id", default="id")
    p.add_argument("--origin-col", default="origin")
    p.add_argument("--facility-col", default="facility")
    p.add_argument("--cost-col", default="cost")
    p.add_argument("--out")
    a = p.parse_args()
    o = duckdb.sql(f'select "{a.id}", "{a.demand}" from \'{a.origins}\'').fetchall()
    f = duckdb.sql(f'select "{a.id}", "{a.capacity}" from \'{a.facilities}\'').fetchall()
    oi = {str(r[0]): i for i, r in enumerate(o)}
    fi = {str(r[0]): j for j, r in enumerate(f)}
    C = np.full((len(o), len(f)), np.inf)
    pairs = duckdb.sql(f'select "{a.origin_col}", "{a.facility_col}", "{a.cost_col}" from \'{a.costs}\'').fetchall()
    skipped = 0
    for oo, ff, c in pairs:
        if str(oo) in oi and str(ff) in fi and c is not None:
            C[oi[str(oo)], fi[str(ff)]] = c
        else:
            skipped += 1
    d = np.array([r[1] for r in o], float)
    s = np.array([r[1] for r in f], float)
    print(f"origins {len(o)} (demand {d.sum():g}), facilities {len(f)} (capacity {s.sum():g}); cost pairs "
          f"{len(pairs)}, not matched {skipped}; pairs without a cost {int((~np.isfinite(C)).sum())}")
    r = solve(C, d, s)
    near = nearest_cost(C, d)
    print(f"total cost {r['cost']:.6g}; with no capacity limit (everyone to the cheapest) {near:.6g} "
          f"(+{100 * (r['cost'] / near - 1):.1f}% for the capacities)" if near > 0 else f"total cost {r['cost']:.6g}")
    full = r["spare"] < 1e-9
    print(f"facilities at capacity {int(full.sum())} of {len(f)}; complementary slackness holds")
    order = np.argsort(-r["capacity_price"])
    for j in order[:10]:
        if r["capacity_price"][j] > 0:
            print(f"  {f[j][0]}: one more unit of capacity saves {r['capacity_price'][j]:.4g}")
    split = int(((r["flows"] > 1e-9).sum(1) > 1).sum())
    print(f"origins split between facilities: {split}; flows integer: "
          f"{bool(np.allclose(r['flows'], np.round(r['flows'])))}")
    if a.out:
        with open(a.out, "w") as fh:
            fh.write("origin,facility,flow,cost\n")
            for i, j in zip(*np.nonzero(r["flows"] > 1e-9)):
                fh.write(f"{o[i][0]},{f[j][0]},{r['flows'][i, j]},{C[i, j]}\n")
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
