"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyarrow --with pytest pytest test_sample_points.py

Small frames whose answers are worked out by hand.
"""

import numpy as np
import pytest

from sample_points import horvitz_thompson_mean, sample

G = np.array([[x, y] for x in range(10) for y in range(10)], float) * 100.0   # 100 candidate sites, 100 m apart


def test_simple_random_takes_n_with_equal_inclusion():
    s = sample(G, "srs", 10, seed=1)
    assert len(s["index"]) == 10 and len(set(s["index"])) == 10
    assert np.allclose(s["inclusion"], 0.1)


def test_stratified_allocation_and_inclusion_by_hand():
    strata = np.array(["A"] * 60 + ["B"] * 40)
    prop = sample(G, "stratified", 10, strata=strata, allocation="proportional", seed=1)
    assert sorted(strata[prop["index"]].tolist()) == ["A"] * 6 + ["B"] * 4
    assert np.allclose(prop["inclusion"], 0.1)
    eq = sample(G, "stratified", 10, strata=strata, allocation="equal", seed=1)
    assert sorted(strata[eq["index"]].tolist()) == ["A"] * 5 + ["B"] * 5
    pi = dict(zip(strata[eq["index"]], eq["inclusion"]))
    assert pi["A"] == pytest.approx(5 / 60) and pi["B"] == pytest.approx(5 / 40)


def test_unequal_inclusion_needs_design_weights():
    strata = np.array(["A"] * 60 + ["B"] * 40)
    y = np.where(strata == "A", 1.0, 3.0)                      # the true mean is (60 x 1 + 40 x 3) / 100 = 1.8
    eq = sample(G, "stratified", 10, strata=strata, allocation="equal", seed=1)
    assert y[eq["index"]].mean() == pytest.approx(2.0)          # five of each: the plain mean is wrong
    assert horvitz_thompson_mean(y[eq["index"]], eq["inclusion"], 100) == pytest.approx(1.8)


def test_cluster_sampling_takes_whole_clusters():
    clusters = np.repeat(np.arange(10), 10)                      # ten clusters of ten
    s = sample(G, "cluster", 3, clusters=clusters, seed=2)
    taken = set(clusters[s["index"]])
    assert len(taken) == 3 and len(s["index"]) == 30
    assert np.allclose(s["inclusion"], 0.3)


def test_grid_sampling_takes_at_most_one_site_per_cell():
    s = sample(G, "grid", 25, seed=3)                            # sites span 0..900 m: cells of sqrt(900^2 / 25) = 180 m
    cells = {tuple(np.floor((G[i] - s["origin"]) / s["cell_m"]).astype(int)) for i in s["index"]}
    assert len(cells) == len(s["index"])
    assert s["cell_m"] == pytest.approx(180.0)


def test_local_pivotal_keeps_n_and_spreads_the_sites():
    from scipy.spatial import cKDTree
    spread = {"srs": [], "lpm": []}
    for seed in range(20):
        for d in spread:
            s = sample(G, d, 10, seed=seed)
            assert len(s["index"]) == 10 and s["inclusion"].sum() == pytest.approx(10 * 10 / 100)
            pts = G[s["index"]]
            spread[d].append(cKDTree(pts).query(pts, 2)[0][:, 1].mean())
    assert np.mean(spread["lpm"]) > 1.2 * np.mean(spread["srs"])   # sites further from each other
