"""Synthetic control for one treated unit: a weighted average of untreated units (donors) whose outcome tracks
the treated unit's before treatment, used as its counterfactual after.

The weights w are non-negative and sum to one, chosen to minimise the squared distance between the treated
unit's pre-treatment outcomes and the donors' weighted outcomes (all pre-treatment periods, equal weight, the
V matrix the identity). With the weights the treated unit is a convex combination of donors: it cannot be
reproduced when it lies outside them (the largest or smallest unit), and the pre-treatment fit says so.

The assumption is that the outcome without treatment follows the same (latent) factors for the treated unit
and its synthetic control after treatment as before, and that donors are not affected by the treatment
(no spillover, no similar treatment of their own).

    synthetic_control   weights, the synthetic path, the gap (treated - synthetic), and the root mean squared
                        gap before (fit) and after treatment
    placebo             in-space placebos: each donor in turn treated as if treated, against the other donors;
                        the treated unit's rank among the ratios post / pre RMSPE, and p = rank / (donors + 1)

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python synth.py TABLE OUTCOME UNIT PERIOD \\
        --treated UNIT_ID --first-treated PERIOD [--donors ID ...] [--exclude ID ...]
"""

import argparse

import numpy as np
from scipy.optimize import nnls


def synth_weights(y1, Y0):
    """argmin ||y1 - Y0 w||^2 subject to w >= 0, sum w = 1: non-negative least squares (an exact active-set
    method) with the sum enforced by one heavily weighted extra row."""
    y1, Y0 = np.asarray(y1, float), np.asarray(Y0, float)
    M = 1e4 * max(1.0, float(np.abs(Y0).max()))
    A = np.vstack([Y0, np.full(Y0.shape[1], M)])
    b = np.r_[y1, M]
    w, _ = nnls(A, b, maxiter=50 * A.shape[1])
    if abs(w.sum() - 1) > 1e-6:
        raise SystemExit(f"the weights sum to {w.sum()}, not 1")
    return w / w.sum()


def synthetic_control(y1, Y0, T0):
    y1, Y0 = np.asarray(y1, float), np.asarray(Y0, float)
    if T0 < 2 or T0 >= len(y1):
        raise SystemExit(f"need at least 2 pre-treatment periods and 1 after; first treated index {T0}")
    if Y0.shape[1] < 2:
        raise SystemExit("need at least 2 donors")
    w = synth_weights(y1[:T0], Y0[:T0])
    path = Y0 @ w
    gap = y1 - path
    return {"w": w, "synthetic": path, "gap": gap, "rmspe_pre": float(np.sqrt(np.mean(gap[:T0] ** 2))),
            "rmspe_post": float(np.sqrt(np.mean(gap[T0:] ** 2))), "effect": float(gap[T0:].mean())}


def placebo(y1, Y0, T0):
    y1, Y0 = np.asarray(y1, float), np.asarray(Y0, float)
    r = synthetic_control(y1, Y0, T0)
    ratios = [r["rmspe_post"] / r["rmspe_pre"]]
    for j in range(Y0.shape[1]):
        others = np.delete(Y0, j, axis=1)
        pj = synthetic_control(Y0[:, j], others, T0)
        ratios.append(pj["rmspe_post"] / pj["rmspe_pre"])
    ratios = np.array(ratios)
    rank = int((ratios >= ratios[0]).sum())
    return {"rank": rank, "p": rank / len(ratios), "ratios": ratios}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("outcome")
    p.add_argument("unit")
    p.add_argument("period")
    p.add_argument("--treated", required=True)
    p.add_argument("--first-treated", type=float, required=True)
    p.add_argument("--donors", nargs="*")
    p.add_argument("--exclude", nargs="*", default=[], help="units that are not donors (aggregates, treated ones)")
    a = p.parse_args()

    import duckdb

    rows = duckdb.sql(f'select "{a.unit}", "{a.period}", "{a.outcome}" from \'{a.table}\'').fetchall()
    units = sorted({str(r[0]) for r in rows})
    periods = sorted({float(r[1]) for r in rows})
    val = {(str(r[0]), float(r[1])): r[2] for r in rows}
    donors = [u for u in (a.donors or units) if u != a.treated and u not in a.exclude]
    keep = [u for u in donors if all(val.get((u, t)) is not None for t in periods)]
    if len(keep) < len(donors):
        print(f"donors dropped for missing periods: {sorted(set(donors) - set(keep))}")
    if any(val.get((a.treated, t)) is None for t in periods):
        raise SystemExit("the treated unit misses periods")
    y1 = np.array([val[(a.treated, t)] for t in periods], float)
    Y0 = np.array([[val[(u, t)] for u in keep] for t in periods], float)
    T0 = sum(t < a.first_treated for t in periods)
    r = synthetic_control(y1, Y0, T0)
    pl = placebo(y1, Y0, T0)
    print(f"treated {a.treated}, donors {len(keep)}, periods {len(periods)} ({T0} before {a.first_treated:g})")
    print("weights above 0.001: " + ", ".join(f"{u} {wt:.3f}" for u, wt in sorted(zip(keep, r["w"]), key=lambda t: -t[1])
                                         if wt > 0.001))
    print(f"pre-treatment RMSPE {r['rmspe_pre']:.4g} (treated outcome sd {y1[:T0].std():.4g}); post RMSPE "
          f"{r['rmspe_post']:.4g}; mean gap after {r['effect']:.4g}")
    print(f"placebo: rank {pl['rank']} of {len(pl['ratios'])} by post/pre RMSPE, p {pl['p']:.3g}")
    for t, g in zip(periods, r["gap"]):
        print(f"  {t:g}: treated {y1[periods.index(t)]:.4g}, synthetic {r['synthetic'][periods.index(t)]:.4g}, "
              f"gap {g:+.4g}")


if __name__ == "__main__":
    main()
