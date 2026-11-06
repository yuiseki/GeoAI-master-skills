"""Which ledger ponds drain through which, on the GSI DEM, and each pond's storage plus all the storage above it.

Pieces (tested in test_cascade_pairs.py):
  fill_holes       DEM5A masks water as NaN. Holes not touching the grid edge are water surfaces: fill each level at
                   its rim's lowest elevation, and label them. Holes touching the edge (sea, missing tiles) stay NaN.
  assign_nodes     a ledger point joins the hole it falls in, or the nearest hole within max_cells; otherwise its cell
                   and 8 neighbours stand for the pond. Points in one hole share one node (one water surface).
  downstream_nodes from each node's outlet (its cell with the largest upstream area), follow the flow to the first
                   cell of another node; None if the flow leaves the grid first.
  cumulative       own storage plus the storage of every node upstream.
  top_only_in_cum  nodes in the top share by cumulative storage but not by own storage.
"""

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / ".agents/skills/terrain-hydrology/scripts"))


def fill_holes(z):
    nan = np.isnan(z)
    lab, _ = ndimage.label(nan)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    out = z.copy()
    labels = np.zeros(z.shape, dtype=np.int32)
    k_out = 0
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None or k in edge:
            continue
        sl = tuple(slice(max(s.start - 1, 0), s.stop + 1) for s in sl)
        hole = lab[sl] == k
        rim = ndimage.binary_dilation(hole) & ~hole & ~nan[sl]
        if not rim.any():
            continue
        k_out += 1
        out[sl][hole] = z[sl][rim].min()
        labels[sl][hole] = k_out
    return out, labels


def assign_nodes(labels, rows, cols, max_cells):
    """Returns the node raster (0 = none), the node id of each point, and how each point was placed."""
    h, w = labels.shape
    dist, (ir, ic) = ndimage.distance_transform_edt(labels == 0, return_indices=True)
    nodes = np.zeros(labels.shape, dtype=np.int64)
    node_of_point, how = [], []
    hole_node = {}
    slices = ndimage.find_objects(labels)
    next_id = 1
    for r, c in zip(rows, cols):
        if not (0 <= r < h and 0 <= c < w):
            node_of_point.append(0)
            how.append("outside")
            continue
        if dist[r, c] <= max_cells:
            hole = int(labels[ir[r, c], ic[r, c]])
            if hole not in hole_node:
                hole_node[hole] = next_id
                sl = slices[hole - 1]
                nodes[sl][labels[sl] == hole] = next_id
                next_id += 1
            node_of_point.append(hole_node[hole])
            how.append("hole")
        else:
            win = nodes[max(r - 1, 0):r + 2, max(c - 1, 0):c + 2]
            win[win == 0] = next_id
            node_of_point.append(next_id)
            how.append("point")
            next_id += 1
    return nodes, np.array(node_of_point), np.array(how)


def downstream_nodes(nodes, fd, lengths=None, cell=5.0):
    """{node: the node its outflow reaches first, or None}. Uses the flow's own upstream area to find each outlet.
    If a dict is passed as lengths, it gets {node: metres along the flow from the outlet to the node below}."""
    upa = fd.upstream_area(unit="cell").ravel()
    ds = fd.idxs_ds
    flat = nodes.ravel()
    idx = np.flatnonzero(flat)
    order = np.argsort(flat[idx], kind="stable")
    idx = idx[order]
    ids, starts = np.unique(flat[idx], return_index=True)
    out = {}
    for n, cells in zip(ids, np.split(idx, starts[1:])):
        cur = int(cells[np.argmax(upa[cells])])
        hit = None
        dist = 0.0
        ncol = nodes.shape[1]
        while ds[cur] != cur:
            nxt = int(ds[cur])
            if nxt < 0:                     # a cell outside the flow network (NoData): the flow stops here
                break
            dist += cell * (1.4142135623730951 if (nxt % ncol != cur % ncol and nxt // ncol != cur // ncol) else 1.0)
            cur = nxt
            m = flat[cur]
            if m != 0 and m != n:
                hit = int(m)
                break
        out[int(n)] = hit
        if lengths is not None and hit is not None:
            lengths[int(n)] = dist
    return out


def cumulative(down, own):
    up = {n: [] for n in down}
    for n, d in down.items():
        if d is not None:
            up.setdefault(d, []).append(n)
    cum, state = {}, {}

    def visit(n):
        if state.get(n) == 1:
            raise ValueError(f"cycle through node {n}")
        if n in cum:
            return cum[n]
        state[n] = 1
        cum[n] = own.get(n, 0.0) + sum(visit(u) for u in up.get(n, []))
        state[n] = 2
        return cum[n]

    for n in down:
        visit(n)
    return cum


def top_only_in_cum(own, cum, share):
    k = max(1, int(round(len(own) * share)))
    top = lambda d: set(sorted(d, key=lambda n: (-d[n], n))[:k])
    return sorted(top(cum) - top(own))


def cumulative_within(down, own, lengths, max_m):
    """Own storage plus the storage of the nodes upstream whose flow reaches this node within max_m metres."""
    up = {}
    for n, d in down.items():
        if d is not None:
            up.setdefault(d, []).append(n)
    out = {}
    for n in down:
        total, stack = own.get(n, 0.0), [(u, lengths[u]) for u in up.get(n, [])]
        while stack:
            u, d = stack.pop()
            if d > max_m:
                continue
            total += own.get(u, 0.0)
            stack.extend((v, d + lengths[v]) for v in up.get(u, []))
        out[n] = total
    return out
