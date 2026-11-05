"""Walking graph from line geometries, structures (bridges), and single-structure cut distances.

Coordinates are planar metres (EPSG:6677 in this project). The graph is undirected. Every vertex of every line is
a node; lines connect only where they share a vertex (the same OSM node gives the same coordinates). Each pair of
consecutive vertices is one edge, tagged with the index of its line, so a structure can be removed by line.
"""
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
import shapely


@dataclass
class Graph:
    xy: np.ndarray        # (n, 2) node coordinates
    u: np.ndarray         # (m,) edge ends
    v: np.ndarray
    length: np.ndarray    # (m,) metres
    line: np.ndarray      # (m,) index of the source line
    comp: np.ndarray      # (n,) connected component label
    main: int             # label of the largest component

    @property
    def n(self):
        return len(self.xy)


def build_graph(geoms, round_m=0.001):
    """geoms: sequence of shapely LineString / MultiLineString. Returns Graph."""
    coords, line_idx, part_idx = [], [], []
    part = 0
    for i, g in enumerate(geoms):
        parts = g.geoms if g.geom_type == "MultiLineString" else [g]
        for p in parts:
            c = np.asarray(p.coords)[:, :2]
            if len(c) < 2:
                continue
            coords.append(c)
            line_idx.append(np.full(len(c), i))
            part_idx.append(np.full(len(c), part))
            part += 1
    if not coords:
        raise ValueError("no lines")
    c = np.vstack(coords)
    li = np.concatenate(line_idx)
    pi = np.concatenate(part_idx)
    key = np.round(c / round_m).astype(np.int64)
    uniq, node = np.unique(key, axis=0, return_inverse=True)
    node = node.ravel()
    xy = uniq * round_m
    same = pi[1:] == pi[:-1]
    u, v = node[:-1][same], node[1:][same]
    length = np.hypot(*(c[1:][same] - c[:-1][same]).T)
    line = li[:-1][same]
    keep = u != v
    u, v, length, line = u[keep], v[keep], length[keep], line[keep]
    n = len(xy)
    adj = csr_matrix((np.ones(len(u)), (u, v)), shape=(n, n))
    _, comp = connected_components(adj, directed=False)
    main = int(np.bincount(comp).argmax())
    return Graph(xy, u, v, length, line, comp, main)


def _matrix(g, edge_mask=None):
    """Symmetric CSR of the kept edges; parallel edges keep the shortest (CSR would sum them)."""
    u, v, w = g.u, g.v, g.length
    if edge_mask is not None:
        u, v, w = u[edge_mask], v[edge_mask], w[edge_mask]
    a, b = np.minimum(u, v), np.maximum(u, v)
    order = np.lexsort((w, b, a))
    a, b, w = a[order], b[order], w[order]
    first = np.ones(len(a), bool)
    first[1:] = (a[1:] != a[:-1]) | (b[1:] != b[:-1])
    a, b, w = a[first], b[first], w[first]
    # zero-length edges would vanish from a sparse matrix; give them a tiny length
    w = np.maximum(w, 1e-6)
    return csr_matrix((np.r_[w, w], (np.r_[a, b], np.r_[b, a])), shape=(g.n, g.n))


def ground_nodes(g, struct_lines, min_component_m=0.0):
    """Nodes with at least one edge that is not part of a structure (bridge or tunnel), and that lie in a component
    of the ground graph (all structure edges removed) whose roads total at least min_component_m.

    The second condition drops small pockets reached only over a structure (platform stairs, a path inside a rail
    yard): an origin snapped there reads as "unreachable" when that structure is cut, though nobody lives there.
    """
    is_struct = np.isin(g.line, np.asarray(sorted(struct_lines), dtype=np.int64))
    ok = np.zeros(g.n, bool)
    ok[g.u[~is_struct]] = True
    ok[g.v[~is_struct]] = True
    if min_component_m > 0:
        u, v, w = g.u[~is_struct], g.v[~is_struct], g.length[~is_struct]
        adj = csr_matrix((np.ones(len(u)), (u, v)), shape=(g.n, g.n))
        _, lab = connected_components(adj, directed=False)
        total = np.bincount(lab[u], weights=w, minlength=lab.max() + 1)
        ok &= total[lab] >= min_component_m
    return ok


def snap(g, pts, main_only=True, allowed=None):
    """Nearest node for each point (planar), among the main component and `allowed` nodes. Returns (node, distance).

    Pass allowed=ground_nodes(...) so that a point is not snapped onto a bridge deck: removing that bridge would
    then cut the point off from everything and read as "unreachable".
    """
    ok = (g.comp == g.main) if main_only else np.ones(g.n, bool)
    if allowed is not None:
        ok &= allowed
    cand = np.flatnonzero(ok)
    tree = cKDTree(g.xy[cand])
    d, i = tree.query(np.asarray(pts))
    return cand[i], d


def multi_source(g, sources, edge_mask=None, limit=np.inf, predecessors=False):
    """Distance from the nearest source to every node."""
    m = _matrix(g, edge_mask)
    src = np.unique(sources)
    if predecessors:
        d, pred, s = dijkstra(m, directed=False, indices=src, min_only=True, limit=limit, return_predecessors=True)
        return d, pred, s
    return dijkstra(m, directed=False, indices=src, min_only=True, limit=limit)


def used_lines(g, pred, origins):
    """Lines whose edges lie on the shortest-path forest from the origins back to their sources."""
    best = {}
    for k in range(len(g.u)):
        a, b = (g.u[k], g.v[k]) if g.u[k] < g.v[k] else (g.v[k], g.u[k])
        if (a, b) not in best or g.length[k] < g.length[best[(a, b)]]:
            best[(a, b)] = k
    seen_nodes = set()
    lines = set()
    for o in np.unique(origins):
        x = int(o)
        while x >= 0 and x not in seen_nodes:
            seen_nodes.add(x)
            p = int(pred[x])
            if p < 0:
                break
            a, b = (p, x) if p < x else (x, p)
            lines.add(int(g.line[best[(a, b)]]))
            x = p
    return lines


def cluster_lines(geoms, idx, dist_m):
    """Group lines (by index) whose geometries lie within dist_m of each other. Returns {line index: group id}."""
    idx = list(idx)
    if not idx:
        return {}
    gs = [geoms[i] for i in idx]
    tree = shapely.STRtree(gs)
    left, right = tree.query(gs, predicate="dwithin", distance=dist_m)
    n = len(idx)
    adj = csr_matrix((np.ones(len(left)), (left, right)), shape=(n, n))
    _, lab = connected_components(adj, directed=False)
    return {idx[k]: int(lab[k]) for k in range(n)}


def cut_distances(g, sources, groups, origins, limit=np.inf):
    """For each group (structure) whose lines lie on an origin's shortest path, the distance with it removed.

    groups: {line index: group id}. Returns d0 (n_origins,), {group id: d_b (n_origins,)} only for groups that
    touch the shortest-path forest (other groups cannot lengthen any origin's shortest path).
    """
    d0_all, pred, _ = multi_source(g, sources, limit=limit, predecessors=True)
    d0 = d0_all[origins]
    on_path = used_lines(g, pred, origins)
    gid_of_line = np.full(g.line.max() + 1, -1)
    for li, gid in groups.items():
        if li < len(gid_of_line):
            gid_of_line[li] = gid
    edge_gid = gid_of_line[g.line]
    hit = {groups[li] for li in on_path if li in groups}
    out = {}
    for gid in sorted(hit):
        d = multi_source(g, sources, edge_mask=edge_gid != gid, limit=limit)
        out[gid] = d[origins]
    return d0, out


def worst_cut(d0, cuts):
    """d* = max over structures, the structure that gives it (-1 if none lengthens), per origin."""
    if not cuts:
        return d0.copy(), np.full(len(d0), -1)
    gids = np.array(sorted(cuts))
    m = np.vstack([cuts[k] for k in gids])
    j = np.argmax(m, axis=0)
    dstar = m[j, np.arange(m.shape[1])]
    who = np.where(dstar > d0 + 1e-6, gids[j], -1)
    dstar = np.maximum(dstar, d0)
    return dstar, who


# ---- spot blockages (a burst pipe, a cave-in, debris): every edge within r of a point is removed ----

def forest_edges(pred, origins):
    """Undirected node pairs on the shortest-path forest from the origins back to their sources."""
    fe = set()
    for x in np.unique(origins):
        x = int(x)
        while pred[x] >= 0:
            p = int(pred[x])
            e = (min(p, x), max(p, x))
            if e in fe:
                break
            fe.add(e)
            x = p
    return fe


def sections(g, pairs):
    """Split the given edges (node pairs) at junctions (nodes of degree != 2 in the whole graph).

    Returns a list of (nodes along the section, midpoint xy). For an origin off the section, blocking it
    anywhere short of its junctions removes the same connection, so its midpoint stands for the whole section.
    For an origin on the section itself, where the block falls decides which way it must leave; only the
    midpoint is tried. A loop with no junction (a block outline whose corners all have degree 2) is one section.
    """
    m = _matrix(g)
    deg = np.diff(m.indptr)
    adj = {}
    for a, b in pairs:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen = set()
    out = []

    def walk(start, nxt):
        path = [start, nxt]
        while deg[path[-1]] == 2 and path[-1] != start:
            cand = [y for y in adj.get(path[-1], []) if y != path[-2]]
            if not cand:
                break
            path.append(cand[0])
        return path

    starts = [n for n in adj if deg[n] != 2] or list(adj)[:1]
    for s in starts:
        for nb in adj[s]:
            if (min(s, nb), max(s, nb)) in seen:
                continue
            path = walk(s, nb)
            for a, b in zip(path, path[1:]):
                seen.add((min(a, b), max(a, b)))
            out.append((path, _midpoint(g.xy[path])))
    # loops made only of degree-2 nodes have no junction to start from
    for a, b in pairs:
        if (a, b) not in seen:
            path = walk(a, b)
            for x, y in zip(path, path[1:]):
                seen.add((min(x, y), max(x, y)))
            out.append((path, _midpoint(g.xy[path])))
    return out


def _midpoint(xy):
    seg = np.hypot(*np.diff(xy, axis=0).T)
    if seg.sum() == 0:
        return xy[0]
    half = seg.sum() / 2
    k = int(np.searchsorted(np.cumsum(seg), half))
    before = np.cumsum(seg)[k] - seg[k]
    t = (half - before) / seg[k] if seg[k] else 0
    return xy[k] + t * (xy[k + 1] - xy[k])


class SpotCutter:
    """Multi-source distances with every edge within r of a point removed, reusing one CSR matrix."""

    def __init__(self, g, sources):
        import shapely
        self.g = g
        self.m = _matrix(g)
        self.src = np.unique(sources)
        # position of each undirected node pair in the CSR data (both directions)
        self.pos = {}
        rows = np.repeat(np.arange(g.n), np.diff(self.m.indptr))
        for k, (i, j) in enumerate(zip(rows, self.m.indices)):
            self.pos.setdefault((min(i, j), max(i, j)), []).append(k)
        self.segs = shapely.linestrings(np.stack([g.xy[g.u], g.xy[g.v]], axis=1))
        self.tree = shapely.STRtree(self.segs)

    def removed_pairs(self, xy, r):
        import shapely
        hit = self.tree.query(shapely.points(xy), predicate="dwithin", distance=r)
        return {(min(int(self.g.u[k]), int(self.g.v[k])), max(int(self.g.u[k]), int(self.g.v[k]))) for k in hit}

    def distances(self, pairs):
        data = self.m.data.copy()
        for p in pairs:
            data[self.pos[p]] = np.inf
        mm = self.m.copy()
        mm.data = data
        return dijkstra(mm, directed=False, indices=self.src, min_only=True)


BIG = 1_000_000


def _zone(g, S, R, L):
    """Distances from S and the edges of the approach zone: inner (an end closer than R), shell (both ends at R or
    more, but not both at R + L or more). Returns d, edge index array, inner mask (over that array), far mask (nodes)."""
    d = multi_source(g, S, limit=R + L + 1.0)
    du, dv = d[g.u], d[g.v]
    near = np.minimum(du, dv)
    keep = near < R + L
    idx = np.flatnonzero(keep)
    inner = near[keep] < R
    far = d >= R + L  # includes unreached (inf)
    return d, idx, inner, far


def approaches(g, S, R=100.0, L=200.0, merge_m=20.0):
    """Approaches to a site entered from the node set S.

    k_e: the most edge-disjoint walks from S to the outside (nodes R + L or more from S); only edges with an end
    closer than R to S can be cut (capacity 1), farther edges are free (capacity BIG). The minimum cut is taken on
    its outer side (the edges nearest the outside), so that two streets meeting at an access node are not read as one
    place. k: the cut edges grouped by merge_m (single linkage); a street drawn as a carriageway and sidewalks is one
    approach. The edge-minimal cut need not have the fewest groups, so k is an upper estimate.
    Returns dict(k_e, k, cut=[edge index], groups=[label per cut edge]).
    """
    from scipy.sparse.csgraph import maximum_flow
    S = np.unique(np.asarray(S, dtype=np.int64))
    d, idx, inner, far = _zone(g, S, R, L)
    u, v = g.u[idx], g.v[idx]
    cap = np.where(inner, 1, BIG).astype(np.int64)
    # parallel copies of a node pair add up (separate ways); self loops are already gone
    nodes = np.unique(np.r_[u, v, S])
    loc = {int(x): i for i, x in enumerate(nodes)}
    lu = np.array([loc[int(x)] for x in u], dtype=np.int64)
    lv = np.array([loc[int(x)] for x in v], dtype=np.int64)
    n = len(nodes)
    s, t = n, n + 1
    fnodes = np.array([loc[int(x)] for x in nodes if far[x]], dtype=np.int64)
    snodes = np.array([loc[int(x)] for x in S], dtype=np.int64)
    if len(fnodes) == 0:
        return dict(k_e=0, k=0, cut=[], groups=[])
    rows = np.r_[lu, lv, np.full(len(snodes), s), fnodes]
    cols = np.r_[lv, lu, snodes, np.full(len(fnodes), t)]
    caps = np.r_[cap, cap, np.full(len(snodes), BIG), np.full(len(fnodes), BIG)]
    m = csr_matrix((caps.astype(np.int32), (rows, cols)), shape=(n + 2, n + 2))
    m.sum_duplicates()
    res = maximum_flow(m, s, t)
    k_e = int(res.flow_value)
    # nodes that still reach t in the residual graph: walk backwards from t over edges with residual > 0
    flow = res.flow.tocsr()
    resid = (m - flow).tocoo()
    pos = resid.data > 0
    back = csr_matrix((np.ones(pos.sum()), (resid.col[pos], resid.row[pos])), shape=(n + 2, n + 2))
    from scipy.sparse.csgraph import breadth_first_order
    reach_t = np.zeros(n + 2, bool)
    reach_t[breadth_first_order(back, t, directed=True, return_predecessors=False)] = True
    cut_mask = inner & (reach_t[lu] != reach_t[lv])
    cut = idx[cut_mask]
    if len(cut) == 0:
        return dict(k_e=k_e, k=0, cut=[], groups=[])
    segs = shapely.linestrings(np.stack([g.xy[g.u[cut]], g.xy[g.v[cut]]], axis=1))
    a, b = shapely.STRtree(segs).query(segs, predicate="dwithin", distance=merge_m)
    _, lab = connected_components(csr_matrix((np.ones(len(a)), (a, b)), shape=(len(cut), len(cut))), directed=False)
    return dict(k_e=k_e, k=int(lab.max() + 1), cut=list(map(int, cut)), groups=list(map(int, lab)))


def single_gate(g, S, R=100.0, L=200.0, r=10.0, return_spots=False):
    """Whether one disk of radius r, centred on a node closer than R to S or on the midpoint of an edge with such an
    end, cuts S off from the outside (R + L or more). Disks holding every node of S shut the site itself and are
    skipped (counted). Returns (closes, n_skipped[, closing centres])."""
    S = np.unique(np.asarray(S, dtype=np.int64))
    d, idx, inner, far = _zone(g, S, R, L)
    u, v = g.u[idx], g.v[idx]
    nodes = np.unique(np.r_[u, v, S])
    loc = np.full(g.n, -1)
    loc[nodes] = np.arange(len(nodes))
    lu, lv = loc[u], loc[v]
    fl = loc[nodes[far[nodes]]]
    sl = loc[S]
    cand = np.vstack([g.xy[nodes[d[nodes] < R]], (g.xy[u[inner]] + g.xy[v[inner]]) / 2])
    segs = shapely.linestrings(np.stack([g.xy[u], g.xy[v]], axis=1))
    tree = shapely.STRtree(segs)
    hits = tree.query(shapely.points(cand), predicate="dwithin", distance=r)
    by_c = np.split(hits[1], np.searchsorted(hits[0], np.arange(1, len(cand))))
    n = len(nodes)
    skipped, closing = 0, []
    for c, removed in zip(cand, by_c):
        if (np.hypot(*(g.xy[S] - c).T) <= r).all():
            skipped += 1
            continue
        keep = np.ones(len(u), bool)
        keep[removed] = False
        adj = csr_matrix((np.ones(keep.sum()), (lu[keep], lv[keep])), shape=(n, n))
        _, lab = connected_components(adj, directed=False)
        if not np.isin(lab[sl], lab[fl]).any():
            closing.append(c)
            if not return_spots:
                break
    closes = len(closing) > 0
    return (closes, skipped, np.array(closing)) if return_spots else (closes, skipped)
