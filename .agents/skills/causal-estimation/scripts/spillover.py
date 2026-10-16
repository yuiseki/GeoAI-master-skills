"""Direct and spillover effects under a known assignment design, by exposure mapping (Aronow and Samii 2017).

Each unit's exposure is its own treatment and whether any neighbour is treated:
    treated, no treated neighbour | treated, treated neighbour | control, treated neighbour |
    control, no treated neighbour
The effects compare mean potential outcomes under two exposures:
    direct     treated with no treated neighbour  -  control with no treated neighbour
    spillover  control with a treated neighbour   -  control with no treated neighbour
The assignment must be known (here: each unit treated independently with probability p, as in a Bernoulli
randomisation). The probability of each exposure for each unit, and for each pair of units, comes from redrawing
the design many times; units on the edge of the map, or with few neighbours, have their own probabilities.

Estimates are Hajek (weighted by 1 / probability of the observed exposure), over the units that can be in both
exposures of the contrast; units that never can are counted. The variance is Aronow and Samii's conservative
estimator (pairs that are never jointly in the exposure are bounded by Young's inequality), applied to the
deviations from the Hajek mean; a contrast's variance is bounded by (sd_1 + sd_0)^2, also conservative.

The exposure mapping is an assumption: spillover that reaches beyond the neighbours, or depends on how many
neighbours are treated, is not captured. Observational (non-designed) treatments are out of scope.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python spillover.py UNITS ID OUTCOME TREATED PAIRS --p 0.3 \\
        [--draws 4000]
        PAIRS: a table (id, neighbour), both directions
"""

import argparse

import numpy as np

CONDITIONS = ["treated, no treated neighbour", "treated, treated neighbour", "control, treated neighbour",
              "control, no treated neighbour"]
DIRECT = ("treated, no treated neighbour", "control, no treated neighbour")
SPILL = ("control, treated neighbour", "control, no treated neighbour")
MAX_UNITS = 3000


def grid_neighbours(side):
    out = []
    for r in range(side):
        for c in range(side):
            out.append(np.array([rr * side + cc for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                                 if 0 <= rr < side and 0 <= cc < side], int))
    return out


def _codes(Z, nb):
    """Exposure codes (index into CONDITIONS) for assignments Z (draws x units)."""
    Z = np.atleast_2d(Z)
    K = np.column_stack([Z[:, j].sum(1) if len(j) else np.zeros(len(Z)) for j in nb])
    return np.where(Z == 1, np.where(K > 0, 1, 0), np.where(K > 0, 2, 3))


def exposure(z, nb):
    return np.array([CONDITIONS[c] for c in _codes(np.asarray(z), nb)[0]])


def exposure_probabilities(nb, p, draws=4000, seed=0):
    n = len(nb)
    if n > MAX_UNITS:
        raise SystemExit(f"{n} units; the joint probabilities are n x n per exposure, up to {MAX_UNITS}")
    Z = (np.random.default_rng(seed).random((draws, n)) < p).astype(int)
    C = _codes(Z, nb)
    pi, joint, never = {}, {}, {}
    for k, name in enumerate(CONDITIONS):
        I = (C == k).astype(float)
        pi[name] = I.mean(0)
        joint[name] = I.T @ I / draws
        never[name] = int((pi[name] == 0).sum())
    return {"pi": pi, "joint": joint, "never": never, "draws": draws, "p": p}


def _hajek(y, ind, pi, pij, eligible):
    m = eligible & ind
    w = 1 / pi[m]
    mu = float((w * y[m]).sum() / w.sum())
    u = np.zeros(len(y))
    u[m] = (y[m] - mu) / pi[m]
    E = eligible.sum()
    idx = np.flatnonzero(m)
    var = (((1 - pi[idx]) * u[idx] ** 2)).sum()
    if len(idx) > 1:
        P = pij[np.ix_(idx, idx)]
        outer = np.outer(pi[idx], pi[idx])
        U = np.outer(u[idx], u[idx]) * outer  # (y_i - mu)(y_j - mu)
        off = ~np.eye(len(idx), dtype=bool)
        pos = off & (P > 0)
        var += ((P[pos] - outer[pos]) / P[pos] * U[pos] / outer[pos]).sum()
        zero = off & (P == 0)
        if zero.any():
            a = (u[idx] ** 2 * pi[idx] / 2)  # Young: |u_i u_j| <= (u_i^2 + u_j^2) / 2, here with 1/pi weights
            var += (zero * (a[:, None] + a[None, :])).sum()
    return mu, float(max(var, 0) / E ** 2)


def estimate(y, z, nb, p, draws=4000, seed=0, probabilities=None):
    y, z = np.asarray(y, float), np.asarray(z, int)
    pr = probabilities or exposure_probabilities(nb, p, draws, seed)
    obs = _codes(z, nb)[0]
    out = {}
    for label, (a, b) in (("direct", DIRECT), ("spillover", SPILL)):
        eligible = (pr["pi"][a] > 0) & (pr["pi"][b] > 0)
        ia, ib = obs == CONDITIONS.index(a), obs == CONDITIONS.index(b)
        if not (eligible & ia).any() or not (eligible & ib).any():
            out[label] = {"value": float("nan"), "se": float("nan"), "units": int(eligible.sum())}
            continue
        ma, va = _hajek(y, ia, pr["pi"][a], pr["joint"][a], eligible)
        mb, vb = _hajek(y, ib, pr["pi"][b], pr["joint"][b], eligible)
        out[label] = {"value": ma - mb, "se": float(np.sqrt(va) + np.sqrt(vb)), "units": int(eligible.sum()),
                      "n_a": int((eligible & ia).sum()), "n_b": int((eligible & ib).sum())}
    out["never"] = pr["never"]
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("units")
    p.add_argument("id")
    p.add_argument("outcome")
    p.add_argument("treated")
    p.add_argument("pairs")
    p.add_argument("--p", type=float, required=True, help="the design's probability of treatment")
    p.add_argument("--draws", type=int, default=4000)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()

    import duckdb

    rows = duckdb.sql(f'select "{a.id}", "{a.outcome}", "{a.treated}" from \'{a.units}\'').fetchall()
    ids = [str(r[0]) for r in rows]
    index = {u: i for i, u in enumerate(ids)}
    pairs = duckdb.sql(f"select id, neighbour from '{a.pairs}'").fetchall()
    nbs = [[] for _ in ids]
    unknown = 0
    for u, v in pairs:
        if str(u) in index and str(v) in index:
            nbs[index[str(u)]].append(index[str(v)])
        else:
            unknown += 1
    nb = [np.array(sorted(set(x)), int) for x in nbs]
    y = np.array([r[1] for r in rows], float)
    z = np.array([r[2] for r in rows], int)
    print(f"units {len(ids)} (treated {int(z.sum())}), neighbour pairs {len(pairs)} ({unknown} with unknown ids), "
          f"units with no neighbour {sum(len(x) == 0 for x in nb)}; design: Bernoulli p {a.p}")
    obs = exposure(z, nb)
    for c in CONDITIONS:
        print(f"  observed {c}: {int((obs == c).sum())}")
    est = estimate(y, z, nb, a.p, a.draws, a.seed)
    print("units that can never be in an exposure: " + ", ".join(f"{k} {v}" for k, v in est["never"].items()))
    naive = y[z == 1].mean() - y[z == 0].mean()
    for label in ("direct", "spillover"):
        r = est[label]
        print(f"{label}: {r['value']:.5g} (conservative se {r['se']:.4g}) over {r['units']} units")
    print(f"naive treated - control difference {naive:.5g} (mixes the direct effect with spillover onto controls)")


if __name__ == "__main__":
    main()
