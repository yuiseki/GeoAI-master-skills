"""Choose where to observe: a sample of sites from a frame of candidate sites, with each site's inclusion
probability.

The frame is the list of sites that could be observed (projected coordinates in metres). Designs:
    srs         simple random sampling, without replacement
    stratified  simple random within strata (--strata), proportional or equal allocation
    cluster     simple random sample of whole clusters (--clusters): n is the number of clusters
    grid        the frame's extent cut into square cells of about area / n, with a random origin; one site at
                random from each cell that holds any (systematic in space; n is approximate)
    lpm         local pivotal method (Grafstrom, Lundstrom and Schelin 2012): equal inclusion n / N, and a
                site rarely sits next to another chosen one (spatially balanced)
    grts        generalized random tessellation stratified (Stevens and Olsen 2004): the extent's square is
                split into quadrants, again and again, until no cell's inclusion probabilities sum above 1;
                the four quadrant digits are shuffled independently inside every parent cell; sites are put
                on a line in the order of their shuffled addresses (ties in random order) with lengths equal
                to their inclusion probabilities; a systematic sample with a random start picks n. Inclusion
                is exactly as given (equal n / N, or proportional to --size), and the order spreads the
                sites in space

local_variance  Grafstrom and Schelin's local mean estimator of the variance of the Horvitz-Thompson total for
                spatially balanced samples: each site's y / pi against the mean over itself and its k nearest
                sampled neighbours. The simple random sampling formula overstates the variance of a balanced
                sample of a smooth surface.

Every chosen site comes with its inclusion probability and design weight (1 / probability). Estimate a mean
with the weights (Horvitz-Thompson), not with the plain mean, whenever probabilities differ.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python sample_points.py FRAME ID X Y --design lpm --n 100 \\
        [--strata COL --allocation proportional|equal] [--clusters COL] [--size COL] [--seed 0] --out sample.parquet
"""

import argparse

import numpy as np

DESIGNS = ("srs", "stratified", "cluster", "grid", "lpm", "grts")


def _grts(xy, p, rng, max_depth=30):
    """p: inclusion probabilities (sum n). Returns the chosen indices."""
    N = len(xy)
    lo = xy.min(0)
    side = float((xy.max(0) - lo).max()) * (1 + 1e-9) + 1e-12
    key = np.zeros(N, dtype=object)  # the shuffled address, as a base-4 number built digit by digit
    cell = np.zeros((N, 2), int)
    open_ = np.ones(N, bool)  # sites in a cell whose probabilities still sum above 1
    for depth in range(1, max_depth + 1):
        if not open_.any():
            break
        scale = 2 ** depth
        sub = np.floor((xy - lo) / side * scale).astype(int)
        quad = (sub[:, 0] % 2) + 2 * (sub[:, 1] % 2)
        perms = {}
        for i in np.nonzero(open_)[0]:
            parent = (cell[i, 0], cell[i, 1])
            if parent not in perms:
                perms[parent] = rng.permutation(4)
            key[i] = key[i] * 4 + int(perms[parent][quad[i]])
            cell[i] = sub[i]
        for i in np.nonzero(~open_)[0]:
            key[i] = key[i] * 4  # a closed cell keeps its place: pad its address
        totals = {}
        for i in np.nonzero(open_)[0]:
            totals[(cell[i, 0], cell[i, 1])] = totals.get((cell[i, 0], cell[i, 1]), 0.0) + p[i]
        for i in np.nonzero(open_)[0]:
            if totals[(cell[i, 0], cell[i, 1])] <= 1 + 1e-12:
                open_[i] = False
    order = sorted(range(N), key=lambda i: (key[i], rng.random()))
    cum = np.cumsum(p[order])
    u = rng.random() + np.arange(int(round(p.sum())))
    picks = np.searchsorted(cum, u, side="right")
    return np.array(order)[picks]


def local_variance(xy, y, inclusion, k=3):
    """Grafstrom and Schelin's local mean variance estimate of the Horvitz-Thompson total (sampled sites only)."""
    xy, y, pi = np.asarray(xy, float), np.asarray(y, float), np.asarray(inclusion, float)
    n = len(y)
    z = y / pi
    d = ((xy[:, None] - xy[None]) ** 2).sum(-1)
    near = np.argsort(d, axis=1)[:, :k + 1]  # itself first
    zbar = z[near].mean(1)
    return float(n / (n - 1) * (k + 1) / k * ((z - zbar) ** 2).sum())


def _lpm(xy, n, rng):
    N = len(xy)
    p = np.full(N, n / N)
    active = np.ones(N, bool)
    while active.sum() > 1:
        idx = np.nonzero(active)[0]
        i = int(rng.choice(idx))
        others = idx[idx != i]
        j = int(others[np.argmin(((xy[others] - xy[i]) ** 2).sum(1))])
        s = p[i] + p[j]
        if s < 1:
            if rng.random() < p[j] / s:
                p[i], p[j] = 0.0, s
            else:
                p[i], p[j] = s, 0.0
        else:
            if rng.random() < (1 - p[j]) / (2 - s):
                p[i], p[j] = 1.0, s - 1
            else:
                p[i], p[j] = s - 1, 1.0
        for k in (i, j):
            if p[k] < 1e-12 or p[k] > 1 - 1e-12:
                p[k] = round(p[k])
                active[k] = False
    for k in np.nonzero(active)[0]:
        p[k] = float(rng.random() < p[k])
    return np.nonzero(p > 0.5)[0]


def sample(xy, design, n, strata=None, allocation="proportional", clusters=None, seed=0, size=None):
    """size (grts): a positive size measure; inclusion proportional to it (capped at 1 by redistributing)."""
    xy = np.asarray(xy, float)
    N = len(xy)
    rng = np.random.default_rng(seed)
    out = {"design": design}
    if design == "srs":
        idx = rng.choice(N, n, replace=False)
        pi = np.full(n, n / N)
    elif design == "stratified":
        strata = np.asarray(strata)
        labels, sizes = np.unique(strata, return_counts=True)
        if allocation == "equal":
            alloc = np.full(len(labels), n // len(labels))
        else:
            alloc = np.floor(n * sizes / N).astype(int)
        alloc[np.argsort(-(n * sizes / N - alloc))[: n - alloc.sum()]] += 1
        idx, pi = [], []
        for lab, size, k in zip(labels, sizes, alloc):
            members = np.nonzero(strata == lab)[0]
            idx += list(rng.choice(members, min(k, size), replace=False))
            pi += [min(k, size) / size] * min(k, size)
        idx, pi = np.array(idx), np.array(pi)
    elif design == "cluster":
        clusters = np.asarray(clusters)
        labels = np.unique(clusters)
        chosen = rng.choice(labels, n, replace=False)
        idx = np.nonzero(np.isin(clusters, chosen))[0]
        pi = np.full(len(idx), n / len(labels))
    elif design == "grid":
        lo, hi = xy.min(0), xy.max(0)
        area = np.prod(hi - lo + 1e-9)
        cell = float(np.sqrt(area / n))
        origin = lo - rng.random(2) * cell
        key = [tuple(c) for c in np.floor((xy - origin) / cell).astype(int)]
        groups = {}
        for i, k in enumerate(key):
            groups.setdefault(k, []).append(i)
        idx, pi = [], []
        for members in groups.values():
            idx.append(rng.choice(members))
            pi.append(1 / len(members))
        idx, pi = np.array(idx), np.array(pi)
        out.update(cell_m=cell, origin=origin)
    elif design == "lpm":
        idx = _lpm(xy, n, rng)
        pi = np.full(len(idx), n / N)
    elif design == "grts":
        if size is None:
            p_all = np.full(N, n / N)
        else:
            size = np.asarray(size, float)
            if (size <= 0).any():
                raise SystemExit("--size must be positive for every site")
            p_all = np.zeros(N)
            free = np.ones(N, bool)
            for _ in range(N):  # sites whose share exceeds 1 are taken for certain; share the rest again
                p_all[free] = (n - (~free).sum()) * size[free] / size[free].sum()
                over = free & (p_all >= 1)
                if not over.any():
                    break
                p_all[over], free[over] = 1.0, False
        idx = _grts(xy, p_all, rng)
        pi = p_all[idx]
        out["inclusion_all"] = p_all
    else:
        raise SystemExit(f"--design must be one of {DESIGNS}")
    out.update(index=np.asarray(idx, int), inclusion=np.asarray(pi, float))
    return out


def horvitz_thompson_mean(y, inclusion, N):
    """Design-weighted estimate of the mean over a frame of N sites."""
    return float(np.sum(np.asarray(y, float) / np.asarray(inclusion, float)) / N)


def main():
    import duckdb
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("frame", "id", "x", "y"):
        p.add_argument(a)
    p.add_argument("--design", required=True, choices=DESIGNS)
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--strata")
    p.add_argument("--allocation", default="proportional", choices=("proportional", "equal"))
    p.add_argument("--clusters")
    p.add_argument("--size", help="grts: a column of positive size measures; inclusion proportional to it")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    cols = [a.id, a.x, a.y] + [c for c in (a.strata, a.clusters, a.size) if c]
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.frame}'").fetchall()
    if any(r[1] is None or r[2] is None for r in rows):
        raise SystemExit("the frame has sites without coordinates; drop them and say so, or fix them")
    xy = np.array([[r[1], r[2]] for r in rows], float)
    extra = {c: np.array([r[3 + i] for r in rows]) for i, c in enumerate(c for c in (a.strata, a.clusters, a.size)
                                                                           if c)}
    s = sample(xy, a.design, a.n, extra.get(a.strata), a.allocation, extra.get(a.clusters), a.seed,
               extra.get(a.size).astype(float) if a.size else None)
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.table({"id": [rows[i][0] for i in s["index"]], "x": xy[s["index"], 0], "y": xy[s["index"], 1],
                             "inclusion": s["inclusion"], "weight": 1 / s["inclusion"]}), a.out)
    print(f"frame {len(rows)} sites, design {a.design}, sample {len(s['index'])}, inclusion "
          f"{s['inclusion'].min():.4g} to {s['inclusion'].max():.4g}")


if __name__ == "__main__":
    main()
