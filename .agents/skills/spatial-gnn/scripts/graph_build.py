"""Build the sensor graph from road distances, and check it before training.

Follows gen_adj_mx.py of the DCRNN repository (Li et al. 2018), without reading its pickle.

  distance_adjacency(rows, ids, k=0.1)  W_ij = exp(-(d_ij / sd)^2) for the directed distances given in rows
                                        (from_id, to_id, distance); sd is the std of the finite distances;
                                        weights below k become 0. Pairs not in rows stay 0
  random_walk(w)                        D_out^-1 W; rows of nodes without out-edges stay 0
  diffusion_supports(w)                 [P_f^T, P_b^T] with P_f = random_walk(w), P_b = random_walk(w^T),
                                        the forward and backward supports of the diffusion convolution
  graph_summary(w)                      nodes, directed edges without the diagonal, nodes with no in-edge,
                                        no out-edge, no edge at all, weak components and the largest share
"""

import numpy as np


def distance_adjacency(rows, ids, k=0.1):
    pos = {int(s): i for i, s in enumerate(ids)}
    d = np.full((len(ids), len(ids)), np.inf)
    for a, b, dist in rows:
        if int(a) in pos and int(b) in pos:
            d[pos[int(a)], pos[int(b)]] = float(dist)
    sd = d[np.isfinite(d)].std()
    w = np.exp(-np.square(d / sd))
    w[w < k] = 0.0
    return w


def random_walk(w):
    deg = w.sum(1)
    inv = np.where(deg > 0, 1.0 / np.where(deg > 0, deg, 1.0), 0.0)
    return inv[:, None] * w


def diffusion_supports(w):
    return [random_walk(w).T, random_walk(w.T).T]


def graph_summary(w):
    a = (np.asarray(w) > 0).astype(int)
    np.fill_diagonal(a, 0)
    n = len(a)
    out_deg, in_deg = a.sum(1), a.sum(0)
    # weak components by a union-find on the undirected edges
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in zip(*np.nonzero(a)):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj
    roots = np.array([find(i) for i in range(n)])
    sizes = np.bincount(np.unique(roots, return_inverse=True)[1])
    return dict(nodes=n, edges=int(a.sum()), no_in=int((in_deg == 0).sum()), no_out=int((out_deg == 0).sum()),
                isolated=int(((in_deg + out_deg) == 0).sum()), components=len(sizes),
                largest_share=float(sizes.max() / n), mean_out_degree=float(out_deg.mean()))
