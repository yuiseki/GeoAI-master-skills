"""Pieces of the stratified fatal-share anomaly analysis (hard-49). Tested by test_fatalshare.py."""
from collections import Counter

import numpy as np


def poibin_sf(p, k):
    """P(X >= k) for X the sum of independent Bernoulli(p_i) (Poisson binomial), by exact recursion."""
    p = np.asarray(p, dtype=float)
    if k <= 0:
        return 1.0
    if k > len(p):
        return 0.0
    dist = np.zeros(len(p) + 1)
    dist[0] = 1.0
    for i, pi in enumerate(p):
        dist[1:i + 2] = dist[1:i + 2] * (1 - pi) + dist[0:i + 1] * pi
        dist[0] *= 1 - pi
    return float(min(1.0, dist[k:].sum()))


def mesh_code(lat, lon, level):
    """JIS X 0410 mesh codes: level 3 = 1 km (8 digits), 4 = 500 m (9), 5 = 250 m (10)."""
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    a = lat * 1.5
    p1 = np.floor(a).astype(int)
    u1 = np.floor(lon).astype(int) - 100
    r1, r2 = (a - p1) * 8, (lon - np.floor(lon)) * 8
    p2, u2 = np.floor(r1).astype(int), np.floor(r2).astype(int)
    s1, s2 = (r1 - p2) * 10, (r2 - u2) * 10
    p3, u3 = np.floor(s1).astype(int), np.floor(s2).astype(int)
    t1, t2 = s1 - p3, s2 - u3
    out = [f"{a_:02d}{b:02d}{c}{d}{e}{f}" for a_, b, c, d, e, f in zip(p1, u1, p2, u2, p3, u3)]
    if level >= 4:
        h1, h2 = (t1 >= 0.5).astype(int), (t2 >= 0.5).astype(int)
        out = [o + str(1 + 2 * x + y) for o, x, y in zip(out, h1, h2)]
        if level >= 5:
            q1 = ((t1 * 2 - h1) >= 0.5).astype(int)
            q2 = ((t2 * 2 - h2) >= 0.5).astype(int)
            out = [o + str(1 + 2 * x + y) for o, x, y in zip(out, q1, q2)]
    return np.array(out)


def mesh_parent(code, level):
    return code[:{3: 8, 4: 9, 5: 10}[level]]


def merge_strata(keys, min_n):
    """Label each row with the finest prefix of its key tuple whose final stratum holds at least min_n rows.

    Bottom up: a group of the finest level with fewer than min_n rows hands its rows to its parent; the parent
    keeps the rows handed to it (not those of children that stayed) and hands them on if they are fewer than
    min_n. Rows that reach the top are labelled '*' (all the rest, whatever their number)."""
    depth = len(keys[0])
    pending = {}
    for i, k in enumerate(keys):
        pending.setdefault(k, []).append(i)
    out = [None] * len(keys)
    for d in range(depth, 0, -1):
        nxt = {}
        for k, rows in pending.items():
            if len(rows) >= min_n:
                for i in rows:
                    out[i] = "|".join(k)
            else:
                nxt.setdefault(k[:d - 1], []).extend(rows)
        pending = nxt
    for rows in pending.values():
        for i in rows:
            out[i] = "*"
    return out


def parent_of(label):
    return "*" if "|" not in label else label.rsplit("|", 1)[0]


def leave_unit_out_p(stratum, unit, fatal, parent):
    """Death probability of each row: the fatal share of its stratum over the rows of other units.
    When no other unit has rows in the stratum, walk up `parent` (label -> parent label, '*' is the top)."""
    stratum, unit, fatal = np.asarray(stratum), np.asarray(unit), np.asarray(fatal, float)
    tot_n, tot_f = Counter(), Counter()
    su_n, su_f = Counter(), Counter()
    # each row also counts toward every ancestor label, so a fallback can use them
    for s, u, f in zip(stratum, unit, fatal):
        lab = s
        while True:
            tot_n[lab] += 1
            tot_f[lab] += f
            su_n[(lab, u)] += 1
            su_f[(lab, u)] += f
            if lab == "*":
                break
            lab = parent.get(lab, parent_of(lab))
    p = np.empty(len(stratum))
    for i, (s, u) in enumerate(zip(stratum, unit)):
        lab = s
        while True:
            n = tot_n[lab] - su_n[(lab, u)]
            if n > 0 or lab == "*":
                p[i] = (tot_f[lab] - su_f[(lab, u)]) / n if n > 0 else np.nan
                break
            lab = parent.get(lab, parent_of(lab))
    return p


def bh(p):
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    q = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out


def overdispersion(unit, fatal, p):
    """T = sum over units of (O - E)^2 / V with E = sum p, V = sum p(1 - p)."""
    unit = np.asarray(unit)
    _, inv = np.unique(unit, return_inverse=True)
    o = np.bincount(inv, weights=np.asarray(fatal, float))
    e = np.bincount(inv, weights=p)
    v = np.bincount(inv, weights=p * (1 - p))
    ok = v > 0
    return float(((o[ok] - e[ok]) ** 2 / v[ok]).sum())


def permute_within(stratum, fatal, rng):
    stratum = np.asarray(stratum)
    out = np.array(fatal, copy=True)
    for s in np.unique(stratum):
        idx = np.flatnonzero(stratum == s)
        out[idx] = out[rng.permutation(idx)]
    return out


def poibin_k_needed(p, alpha):
    """Smallest k with P(X >= k) <= alpha for the Poisson binomial of p; len(p) + 1 when no k reaches it."""
    p = np.asarray(p, dtype=float)
    dist = np.zeros(len(p) + 1)
    dist[0] = 1.0
    for i, pi in enumerate(p):
        dist[1:i + 2] = dist[1:i + 2] * (1 - pi) + dist[0:i + 1] * pi
        dist[0] *= 1 - pi
    sf = np.cumsum(dist[::-1])[::-1]  # sf[k] = P(X >= k)
    ok = np.flatnonzero(sf <= alpha)
    return int(ok[0]) if len(ok) else len(p) + 1


def build_links(ways):
    """Junction-to-junction road links: node all ways where they meet or cross, then merge at degree-2 points."""
    import shapely
    noded = shapely.union_all(np.asarray(ways, dtype=object))
    merged = shapely.line_merge(noded)
    parts = shapely.get_parts(merged)
    return [g for g in parts if g.length > 0]


def assign_nearest(links, xy, max_m):
    """Index of the nearest link for each point, -1 when none lies within max_m."""
    import shapely
    tree = shapely.STRtree(np.asarray(links, dtype=object))
    pts = shapely.points(np.asarray(xy, float))
    pi, li = tree.query_nearest(pts, max_distance=max_m, all_matches=False)
    out = np.full(len(pts), -1, dtype=int)
    out[pi] = li
    return out


def leave_unit_out_p_shrunk(stratum, unit, fatal, m):
    """Leave-unit-out stratum share pulled toward its parent's: p_s = (F_s + m p_parent) / (N_s + m), each level
    over the rows of other units, recursively up to '*' (not pulled). With m = 0 and rows left, the plain share."""
    stratum, unit, fatal = np.asarray(stratum), np.asarray(unit), np.asarray(fatal, float)
    tot_n, tot_f, su_n, su_f = Counter(), Counter(), Counter(), Counter()
    for s, u, f in zip(stratum, unit, fatal):
        lab = s
        while True:
            tot_n[lab] += 1
            tot_f[lab] += f
            su_n[(lab, u)] += 1
            su_f[(lab, u)] += f
            if lab == "*":
                break
            lab = parent_of(lab)
    cache = {}

    def rate(lab, u):
        key = (lab, u)
        if key not in cache:
            n = tot_n[lab] - su_n[key]
            f = tot_f[lab] - su_f[key]
            if lab == "*":
                cache[key] = f / n if n > 0 else np.nan
            else:
                pp = rate(parent_of(lab), u)
                cache[key] = (f + m * pp) / (n + m) if n + m > 0 else pp
        return cache[key]

    return np.array([rate(s, u) for s, u in zip(stratum, unit)])
