"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with networkx --with pytest pytest test_transport_crosscheck.py

The LP (HiGHS) against networkx's network simplex (min_cost_flow): a different algorithm on the same flow
network (a source to origins with their demands, origins to facilities at the pair costs, facilities to a sink
with their capacities). networkx wants integer costs and amounts; the total costs must agree exactly.
"""

import numpy as np
import pytest

from transport import solve

nx = pytest.importorskip("networkx")


def _network_cost(C, d, s):
    G = nx.DiGraph()
    n, m = C.shape
    G.add_node("src", demand=-int(d.sum()))
    G.add_node("sink", demand=int(d.sum()))
    for i in range(n):
        G.add_edge("src", ("o", i), capacity=int(d[i]), weight=0)
        for j in range(m):
            G.add_edge(("o", i), ("f", j), weight=int(C[i, j]))
    for j in range(m):
        G.add_edge(("f", j), "sink", capacity=int(s[j]), weight=0)
    flow = nx.min_cost_flow(G)
    return nx.cost_of_flow(G, flow)


@pytest.mark.parametrize("seed", range(6))
def test_total_cost_matches_networkx_network_simplex(seed):
    rng = np.random.default_rng(seed)
    n, m = 25, 6
    C = rng.integers(1, 100, (n, m)).astype(float)
    d = rng.integers(1, 20, n).astype(float)
    s = rng.integers(int(d.sum() / m * 0.8), int(d.sum() / m * 1.6), m).astype(float)
    if s.sum() < d.sum():
        s[0] += d.sum() - s.sum()
    assert solve(C, d, s)["cost"] == pytest.approx(_network_cost(C, d, s), abs=1e-6)
