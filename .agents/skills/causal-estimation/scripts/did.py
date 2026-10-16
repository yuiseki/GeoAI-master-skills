"""Difference in differences on a balanced panel of units observed over periods, some treated from a period on
(the cohort) and some never treated. The assumption is parallel trends: without treatment, each cohort's mean
would have moved like the never-treated mean. Nothing here makes it true; the pre-treatment cells test a part
of it.

    two_by_two  (treated after - treated before) - (control after - control before)
    twfe        the coefficient of the treatment indicator in a regression with unit and period fixed effects
                (within transformation by alternating demeaning), standard error clustered by unit (CR1). With
                staggered adoption and effects that change over time, it averages comparisons that use already
                treated units as controls, and can be far from every true effect.
    att_gt      Callaway and Sant'Anna's group-time effects with never-treated units as the comparison:
                ATT(g, t) = mean over cohort g of (y_t - y_base) - the same for the never treated, with base the
                period before g for t >= g (minus --anticipation) and the period before t for t < g (so the
                pre-treatment cells are period-to-period changes). --boot resamples whole units.
    aggregate   simple: post-treatment cells averaged with weights proportional to cohort size; event: cells
                grouped by t - g (event time), the same weights within each event time.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python did.py TABLE OUTCOME UNIT PERIOD COHORT [--boot 499]
        COHORT is the first treated period of the unit, 0 for never treated.
"""

import argparse

import numpy as np


def two_by_two(y, treated, post):
    y, g, p = np.asarray(y, float), np.asarray(treated, int), np.asarray(post, int)
    m = {(a, b): y[(g == a) & (p == b)].mean() for a in (0, 1) for b in (0, 1)}
    return {"did": float((m[1, 1] - m[1, 0]) - (m[0, 1] - m[0, 0])), "means": m}


def _demean(v, groups, tol=1e-12, maxiter=10_000):
    v = np.asarray(v, float).copy()
    codes = [np.unique(gr, return_inverse=True)[1] for gr in groups]
    for _ in range(maxiter):
        prev = v.copy()
        for c in codes:
            v -= (np.bincount(c, v) / np.bincount(c))[c]
        if np.abs(v - prev).max() < tol:
            return v
    raise SystemExit("demeaning did not converge")


def twfe(y, unit, time, d):
    y, d = np.asarray(y, float), np.asarray(d, float)
    yt, dt = _demean(y, [unit, time]), _demean(d, [unit, time])
    if (dt ** 2).sum() == 0:
        raise SystemExit("the treatment indicator does not vary within units and periods")
    b = float((yt * dt).sum() / (dt ** 2).sum())
    e = yt - b * dt
    u = np.unique(unit, return_inverse=True)[1]
    G, N = u.max() + 1, len(y)
    score = np.bincount(u, dt * e)
    # CR1 as pyfixest 0.60 does by default: unit effects are nested in the clusters and not counted; every
    # period effect and the coefficient are.
    K = 1 + len(np.unique(time))
    v = (score ** 2).sum() / (dt ** 2).sum() ** 2 * G / (G - 1) * (N - 1) / (N - K)
    return {"coef": b, "se": float(np.sqrt(v)), "clusters": int(G)}


def _panel(y, unit, time, cohort):
    units, ui = np.unique(unit, return_inverse=True)
    periods, ti = np.unique(time, return_inverse=True)
    if len(y) != len(units) * len(periods) or len(set(zip(ui, ti))) != len(y):
        raise SystemExit(f"the panel is not balanced: {len(y)} rows for {len(units)} units x {len(periods)} periods")
    Y = np.full((len(units), len(periods)), np.nan)
    Y[ui, ti] = y
    G = np.zeros(len(units))
    G[ui] = cohort
    for i in range(len(units)):
        if len(set(np.asarray(cohort)[ui == i])) != 1:
            raise SystemExit(f"unit {units[i]} has more than one cohort")
    if not (G == 0).any():
        raise SystemExit("no never-treated units (cohort 0) to compare with")
    return Y, G, periods


def _cells(Y, G, periods, anticipation):
    pos = {p: i for i, p in enumerate(periods)}
    never = G == 0
    out = []
    for g in sorted(set(G[G > 0])):
        for t in periods[1:]:
            base = (g - 1 - anticipation) if t >= g else periods[pos[t] - 1]
            if base not in pos:
                continue
            m = G == g
            dg = Y[m, pos[t]] - Y[m, pos[base]]
            dn = Y[never, pos[t]] - Y[never, pos[base]]
            out.append({"g": g, "t": t, "base": base, "att": float(dg.mean() - dn.mean()), "n_g": int(m.sum())})
    return out


def att_gt(y, unit, time, cohort, boot=0, seed=0, anticipation=0):
    Y, G, periods = _panel(np.asarray(y, float), np.asarray(unit), np.asarray(time), np.asarray(cohort, float))
    cells = _cells(Y, G, periods, anticipation)
    if boot:
        rng = np.random.default_rng(seed)
        draws = np.empty((boot, len(cells)))
        n = len(G)
        b = 0
        while b < boot:
            idx = rng.integers(0, n, n)
            if not (G[idx] == 0).any():
                continue
            sub = _cells(Y[idx], G[idx], periods, anticipation)
            if len(sub) != len(cells):  # a cohort missing from the draw
                continue
            draws[b] = [c["att"] for c in sub]
            b += 1
        for j, c in enumerate(cells):
            c["draws"] = draws[:, j]
    return cells


def _combine(cells):
    w = np.array([c["n_g"] for c in cells], float)
    att = float((w * [c["att"] for c in cells]).sum() / w.sum())
    se = float("nan")
    if cells and "draws" in cells[0]:
        D = np.column_stack([c["draws"] for c in cells])
        se = float((D @ w / w.sum()).std(ddof=1))
    return {"att": att, "se": se, "cells": len(cells)}


def aggregate(cells, kind="simple"):
    if kind == "simple":
        return _combine([c for c in cells if c["t"] >= c["g"]])
    if kind == "event":
        es = sorted({int(c["t"] - c["g"]) for c in cells})
        return {e: _combine([c for c in cells if c["t"] - c["g"] == e]) for e in es}
    raise SystemExit(f"unknown aggregation {kind}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("outcome")
    p.add_argument("unit")
    p.add_argument("period")
    p.add_argument("cohort")
    p.add_argument("--boot", type=int, default=499)
    p.add_argument("--anticipation", type=int, default=0)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()

    import duckdb

    rows = duckdb.sql(f'select "{a.outcome}", "{a.unit}", "{a.period}", "{a.cohort}" from \'{a.table}\'').fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("missing values; the panel must be complete")
    y = np.array([r[0] for r in rows], float)
    unit = np.array([str(r[1]) for r in rows])
    time = np.array([r[2] for r in rows], float)
    cohort = np.array([r[3] for r in rows], float)
    d = ((cohort > 0) & (time >= cohort)).astype(float)
    Y, G, periods = _panel(y, unit, time, cohort)
    print(f"rows {len(y)}: units {len(G)} (never treated {int((G == 0).sum())}, cohorts "
          f"{ {int(g): int((G == g).sum()) for g in sorted(set(G[G > 0]))} }), periods {len(periods)}")
    tw = twfe(y, unit, time, d)
    print(f"TWFE coefficient {tw['coef']:.5g} (se clustered by unit {tw['se']:.3g}); with staggered adoption and "
          "changing effects this is not an average of the cell effects below")
    cells = att_gt(y, unit, time, cohort, a.boot, a.seed, a.anticipation)
    s = aggregate(cells, "simple")
    print(f"group-time (never-treated comparison), simple aggregate ATT {s['att']:.5g} (unit bootstrap se {s['se']:.3g}, "
          f"{s['cells']} post cells)")
    print("event time: ATT (se)")
    for e, r in aggregate(cells, "event").items():
        print(f"  {e:+d}: {r['att']:+.5g} ({r['se']:.3g}){'  <- before treatment' if e < 0 else ''}")


if __name__ == "__main__":
    main()
