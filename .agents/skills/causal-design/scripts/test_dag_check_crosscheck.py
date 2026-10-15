"""uvx --with numpy --with networkx --with pgmpy --with pytest pytest test_dag_check_crosscheck.py

dag_check against networkx's d-separation and pgmpy's backdoor adjustment sets on 300 random DAGs. The backdoor
criterion holds for Z when no member of Z descends from T and Z d-separates T and Y once T's outgoing arrows
are removed; networkx decides the d-separation independently of dag_check's path walk.
"""

from itertools import combinations

import networkx as nx
import numpy as np
import pytest

from dag_check import Dag


def _cases(count=300, seed=0, n=8, p=0.3):
    """Random DAGs on 8 variables; T and Y any pair in causal order, about a fifth of the rest unmeasured.
    T need not cause Y: a valid set must then show no effect. Rare shapes (a measured descendant of a collider
    on a backdoor path) appear only when T and Y are not forced to be adjacent."""
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < count:
        order = [f"V{i}" for i in rng.permutation(n)]
        edges = [(order[i], order[j]) for i in range(n) for j in range(i + 1, n) if rng.random() < p]
        i, j = sorted(rng.choice(n, 2, replace=False))
        t, y = order[i], order[j]
        nodes = {v for e in edges for v in e}
        if t not in nodes or y not in nodes:
            continue
        latent = {v for v in nodes if v not in (t, y) and rng.random() < 0.2}
        out.append((edges, latent, t, y))
    return out


CASES = _cases()


def _backdoor_valid_nx(g, t, y, z):
    if set(z) & nx.descendants(g, t):
        return False
    cut = g.copy()
    cut.remove_edges_from(list(g.out_edges(t)))
    return nx.is_d_separator(cut, {t}, {y}, set(z))


def test_every_adjustment_set_is_judged_as_networkx_judges_it():
    checked = 0
    for edges, latent, t, y in CASES:
        g = nx.DiGraph(edges)
        d = Dag(edges, latent)
        observed = [v for v in g.nodes if v not in (t, y) and v not in latent]
        for k in range(len(observed) + 1):
            for z in combinations(observed, k):
                assert d.check(t, y, z)["valid"] == _backdoor_valid_nx(g, t, y, z), (edges, latent, t, y, z)
                checked += 1
    assert checked == 8314  # every subset of the measured variables, over the 300 graphs


def test_minimal_sets_match_an_enumeration_by_networkx():
    for edges, latent, t, y in CASES:
        g = nx.DiGraph(edges)
        observed = [v for v in sorted(g.nodes) if v not in (t, y) and v not in latent and v not in nx.descendants(g, t)]
        valid = [set(z) for k in range(len(observed) + 1) for z in combinations(observed, k)
                 if _backdoor_valid_nx(g, t, y, z)]
        minimal = sorted(sorted(z) for z in valid if not any(o < z for o in valid))
        assert sorted(Dag(edges, latent).adjustment_sets(t, y)) == minimal


def test_minimal_sets_match_pgmpy_without_latent_variables():
    pgmpy = pytest.importorskip("pgmpy")
    from pgmpy.base import DAG
    from pgmpy.inference import CausalInference

    compared = 0
    for edges, _, t, y in CASES[:150]:
        ci = CausalInference(DAG(edges))
        theirs = sorted(sorted(s) for s in ci.get_all_backdoor_adjustment_sets(t, y))
        ours = [s for s in Dag(edges).adjustment_sets(t, y) if s]  # pgmpy omits the empty set
        if not theirs and ours == []:
            compared += 1
            continue
        assert sorted(ours) == theirs, (edges, t, y)
        compared += 1
    assert compared == 150
