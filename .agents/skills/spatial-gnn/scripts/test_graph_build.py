"""uvx --python 3.12 --with numpy --with pytest pytest -q test_graph_build.py"""

import numpy as np
import pytest

from graph_build import diffusion_supports, distance_adjacency, graph_summary, random_walk


def test_distance_adjacency_uses_the_gaussian_kernel_and_the_cutoff():
    ids = [1, 2, 3]
    rows = [(1, 1, 0.0), (1, 2, 1.0), (2, 3, 10.0), (9, 1, 1.0)]   # sensor 9 is not in ids
    a = distance_adjacency(rows, ids, k=0.1)
    sd = np.array([0.0, 1.0, 10.0]).std()
    assert a[0, 0] == 1.0 and a[0, 1] == pytest.approx(np.exp(-(1 / sd) ** 2))
    assert a[1, 0] == 0.0                                   # directed: no distance from 2 to 1
    w23 = np.exp(-(10 / sd) ** 2)
    assert a[1, 2] == (w23 if w23 >= 0.1 else 0.0)
    assert a[2, 2] == 0.0                                   # the diagonal only where a distance is given


def test_random_walk_rows_sum_to_one_or_zero():
    p = random_walk(np.array([[0, 2.0, 2.0], [1.0, 0, 0], [0, 0, 0]]))
    assert np.allclose(p.sum(1), [1, 1, 0]) and p[0, 1] == pytest.approx(0.5)


def test_supports_carry_the_value_along_and_against_the_edges():
    w = np.zeros((3, 3))
    w[0, 1] = w[1, 2] = 1.0                                 # 0 -> 1 -> 2
    fwd, bwd = diffusion_supports(w)
    x = np.array([1.0, 0.0, 0.0])
    assert np.allclose(fwd @ x, [0, 1, 0])                  # downstream node 1 hears from 0
    assert np.allclose(bwd @ np.array([0, 0, 1.0]), [0, 1, 0])  # upstream node 1 hears from 2


def test_graph_summary_counts_isolated_nodes_and_components():
    w = np.eye(5)
    w[0, 1] = w[1, 2] = 0.5                                 # 0-1-2 joined, 3 and 4 alone
    s = graph_summary(w)
    assert s["edges"] == 2 and s["isolated"] == 2 and s["components"] == 3
    assert s["no_in"] == 3 and s["no_out"] == 3 and s["largest_share"] == pytest.approx(0.6)
