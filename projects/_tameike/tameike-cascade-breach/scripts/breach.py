"""Pieces of the screen in EXPERIMENT_PLAN.md, tested in test_breach.py.

  froehlich, macdonald   peak breach outflow (m3/s) from the volume released V (m3) and the head h (m)
                         (Froehlich 1995b; MacDonald and Langridge-Monopolis 1984; both as tabled in Wahl 2004)
  spillway_capacity      design flood of a pond's spillway by the rational formula, times a margin (1.2 in the
                         land improvement design guideline for ponds): margin x (1/3.6) x f x r (mm/h) x A (km2)
  excess_volume          volume of a triangular inflow (peak qp, volume v) above a constant outflow qc
  gumbel_lmoments        Gumbel location and scale from a sample by L-moments; gumbel_quantile for a return period
  gev_lmoments           GEV location, scale and shape by L-moments (Hosking 1990, k > 0 is a bounded upper tail);
                         gev_quantile for a return period
  run_chain              from one pond's breach, the ponds below that overflow one after another
"""

import math

import numpy as np

EULER = 0.5772156649015329


def froehlich(v, h):
    return 0.607 * v ** 0.295 * h ** 1.24


def macdonald(v, h):
    return 1.154 * (v * h) ** 0.412


def spillway_capacity(f, r_mm_h, area_km2, margin=1.2):
    return margin * f * r_mm_h * area_km2 / 3.6


def excess_volume(v, qp, qc):
    if qp <= qc:
        return 0.0
    return v * (1.0 - qc / qp) ** 2


def gumbel_lmoments(x):
    x = np.sort(np.asarray(x, dtype="float64"))
    n = len(x)
    b0 = x.mean()
    b1 = np.sum((np.arange(n)) / (n - 1) * x) / n
    l1, l2 = b0, 2 * b1 - b0
    beta = l2 / math.log(2)
    return l1 - EULER * beta, beta


def gumbel_quantile(mu, beta, period):
    return mu - beta * math.log(-math.log(1 - 1 / period))


def _lmoments(x):
    x = np.sort(np.asarray(x, dtype="float64"))
    n = len(x)
    i = np.arange(n)
    b0 = x.mean()
    b1 = np.sum(i / (n - 1) * x) / n
    b2 = np.sum(i * (i - 1) / ((n - 1) * (n - 2)) * x) / n
    return b0, 2 * b1 - b0, 6 * b2 - 6 * b1 + b0


def gev_lmoments(x):
    l1, l2, l3 = _lmoments(x)
    t3 = l3 / l2
    c = 2 / (3 + t3) - math.log(2) / math.log(3)
    k = 7.8590 * c + 2.9554 * c * c
    alpha = l2 * k / ((1 - 2 ** (-k)) * math.gamma(1 + k))
    xi = l1 - alpha * (1 - math.gamma(1 + k)) / k
    return xi, alpha, k


def gev_quantile(xi, alpha, k, period):
    return xi + alpha * (1 - (-math.log(1 - 1 / period)) ** k) / k


def run_chain(start, down, ponds, params):
    """ponds[n]: dict(v=m3, h=m, s=m2 or None, a=km2, dist=m to the pond below or None).
    params: f, r, margin, freeboard, max_dist, peak (a function of v and h).
    Returns (failed ponds below the start, in order; why the chain stopped)."""
    p0 = ponds[start]
    if not p0["v"] or not p0["h"]:
        return [], "start has no volume or height"
    released, cur, failed = p0["v"], start, []
    qp = params["peak"](released, p0["h"])
    while True:
        nxt = down.get(cur)
        if nxt is None:
            return failed, "flow leaves the area or reaches no pond"
        if ponds[cur]["dist"] is None or ponds[cur]["dist"] > params["max_dist"]:
            return failed, "next pond beyond the distance"
        d = ponds[nxt]
        if d["s"] is None or d["a"] is None:
            return failed, "next pond has no water surface"
        qc = spillway_capacity(params["f"], params["r"], d["a"], params["margin"])
        rise = excess_volume(released, qp, qc) / d["s"]
        if rise <= params["freeboard"]:
            return failed, "next pond holds"
        failed.append(nxt)
        if not d["h"]:
            return failed, "overflowing pond has no height"
        released = released + (d["v"] or 0.0)
        qp = params["peak"](released, d["h"])
        cur = nxt
