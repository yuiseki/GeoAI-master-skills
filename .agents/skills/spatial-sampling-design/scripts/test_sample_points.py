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


# GRTS and the local mean variance estimator

def _frame(seed=0, N=300):
    rng = np.random.default_rng(seed)
    return rng.uniform(0, 1000, (N, 2))


def test_grts_takes_n_and_its_inclusion_frequencies_match_n_over_N():
    xy = _frame()
    hits = np.zeros(300)
    for s in range(3000):
        idx = sample(xy, "grts", 30, seed=s)["index"]
        assert len(idx) == 30 and len(set(idx.tolist())) == 30
        hits[idx] += 1
    freq = hits / 3000
    # 0.1 each; a binomial sd of sqrt(0.1 * 0.9 / 3000) = 0.0055 per site, 300 sites
    assert np.abs(freq - 0.1).max() < 6 * 0.0055
    assert freq.mean() == pytest.approx(0.1, abs=1e-12)


def test_grts_with_a_size_measure_gives_inclusion_proportional_to_size():
    xy = _frame(1, 100)
    size = np.r_[np.full(50, 1.0), np.full(50, 3.0)]
    s0 = sample(xy, "grts", 20, seed=0, size=size)
    np.testing.assert_allclose(s0["inclusion_all"], 20 * size / size.sum())
    hits = np.zeros(100)
    for s in range(4000):
        hits[sample(xy, "grts", 20, seed=s, size=size)["index"]] += 1
    assert hits[:50].mean() / 4000 == pytest.approx(0.1, abs=0.006)
    assert hits[50:].mean() / 4000 == pytest.approx(0.3, abs=0.008)


def _voronoi_balance(xy, idx, pi_all):
    # Stevens and Olsen's balance: the frame's inclusion probabilities summed over each sampled site's
    # (discrete) Voronoi cell; 1 for each under perfect balance. Returns their variance.
    d = ((xy[:, None] - xy[idx][None]) ** 2).sum(-1)
    owner = d.argmin(1)
    return float(np.var(np.bincount(owner, weights=pi_all, minlength=len(idx))))


def test_grts_and_lpm_are_more_balanced_than_simple_random_sampling():
    xy = _frame(2)
    pi = np.full(300, 0.1)
    bal = {d: np.mean([_voronoi_balance(xy, sample(xy, d, 30, seed=s)["index"], pi) for s in range(100)])
           for d in ("srs", "grts", "lpm")}
    assert bal["grts"] < 0.5 * bal["srs"] and bal["lpm"] < 0.5 * bal["srs"]


def test_the_local_variance_estimator_tracks_the_design_variance_where_the_srs_formula_overstates_it():
    from sample_points import local_variance

    xy = _frame(3)
    y = np.sin(xy[:, 0] / 200) + np.cos(xy[:, 1] / 300) + 0.1 * np.random.default_rng(0).normal(size=300)
    totals, local, srs = [], [], []
    for s in range(800):
        r = sample(xy, "grts", 30, seed=s)
        i, pi = r["index"], r["inclusion"]
        totals.append(np.sum(y[i] / pi))
        local.append(local_variance(xy[i], y[i], pi))
        srs.append(300 ** 2 * (1 - 30 / 300) * np.var(y[i], ddof=1) / 30)
    true = np.var(totals)
    assert np.mean(local) == pytest.approx(true, rel=0.15)  # measured 289 against 278
    assert np.mean(srs) > 2 * true  # measured 2,660: the SRS formula ignores the balance


def test_the_local_variance_estimator_understates_the_variance_of_a_simple_random_sample():
    # The estimator sees only local differences; an unbalanced sample's total also varies with the large-scale
    # pattern it happens to hit. Measured: 288 against a true 2,625.
    from sample_points import local_variance

    xy = _frame(3)
    y = np.sin(xy[:, 0] / 200) + np.cos(xy[:, 1] / 300) + 0.1 * np.random.default_rng(0).normal(size=300)
    totals, local = [], []
    for s in range(400):
        r = sample(xy, "srs", 30, seed=s)
        i, pi = r["index"], r["inclusion"]
        totals.append(np.sum(y[i] / pi))
        local.append(local_variance(xy[i], y[i], pi))
    assert np.mean(local) < 0.3 * np.var(totals)
