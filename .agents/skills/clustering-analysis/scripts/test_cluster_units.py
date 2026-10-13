"""uvx --with duckdb --with scikit-learn --with pytest pytest test_cluster_units.py"""

import numpy as np
import pytest
from sklearn.metrics import adjusted_rand_score

from cluster_units import cluster, external_agreement, spatial_cohesion, stability


def blobs(seed=0, n=90):
    rng = np.random.default_rng(seed)
    centres = np.array([[0, 0], [6, 0], [0, 6]])
    truth = np.repeat([0, 1, 2], n // 3)
    X = centres[truth] + rng.normal(scale=0.7, size=(n, 2))
    return X, truth


@pytest.mark.parametrize("method,params", [
    ("kmeans", {"k": 3}),
    ("hdbscan", {"min_cluster_size": 10}),
    ("dbscan", {"eps": 0.5, "min_samples": 5}),  # eps in standardised units
    ("dpmm", {"max_components": 8}),
])
def test_every_method_recovers_separated_blobs(method, params):
    X, truth = blobs()
    labels = cluster(X, method, params, seed=0)
    keep = labels >= 0  # density methods may call a few points noise (-1)
    assert keep.mean() > 0.9
    assert adjusted_rand_score(truth[keep], labels[keep]) > 0.9


def test_features_are_standardised_before_clustering():
    # The groups differ only in a small-scale feature; a large-scale noise feature would dominate
    # distances if the features were not put on the same scale.
    rng = np.random.default_rng(1)
    truth = np.repeat([0, 1], 50)
    X = np.c_[truth * 5 + rng.normal(size=100), rng.normal(scale=1000, size=100)]
    labels = cluster(X, "kmeans", {"k": 2}, seed=0)
    assert adjusted_rand_score(truth, labels) > 0.9


def test_stability_is_high_for_blobs_and_lower_for_structureless_data():
    X, _ = blobs()
    s_blobs = stability(X, "kmeans", {"k": 3}, runs=10, fraction=0.8, seed=0)
    rng = np.random.default_rng(2)
    U = rng.uniform(size=(90, 2))
    s_unif = stability(U, "kmeans", {"k": 6}, runs=10, fraction=0.8, seed=0)
    assert s_blobs["ari_mean"] > 0.95
    assert s_unif["ari_mean"] < s_blobs["ari_mean"] - 0.1


def test_stability_compares_only_the_units_both_runs_saw():
    X, _ = blobs()
    s = stability(X, "kmeans", {"k": 3}, runs=3, fraction=0.5, seed=0)
    assert s["units_per_run"] == 45


def test_external_agreement():
    _, truth = blobs()
    names = np.array(["a", "b", "c"])[truth]
    assert external_agreement(truth, names) == pytest.approx(1.0)


def test_spatial_cohesion_tells_map_clusters_from_scattered_ones():
    rng = np.random.default_rng(3)
    lon = rng.uniform(-20, 20, 200)
    lat = rng.uniform(40, 60, 200)
    by_side = (lon > 0).astype(int)
    scattered = rng.integers(0, 2, 200)
    c_side = spatial_cohesion(by_side, lon, lat, k=6, permutations=199, seed=0)
    c_scat = spatial_cohesion(scattered, lon, lat, k=6, permutations=199, seed=0)
    assert c_side["same_share"] > 0.9 and c_side["p_sim"] <= 0.01
    assert abs(c_scat["same_share"] - c_scat["expected_share"]) < 0.05
    assert c_scat["p_sim"] > 0.05


def test_no_clusters_is_not_reported_as_perfectly_stable():
    # HDBSCAN with a minimum cluster size larger than any group calls every unit noise. Every run
    # then agrees perfectly, which must not read as a stable clustering.
    X, _ = blobs()
    labels = cluster(X, "hdbscan", {"min_cluster_size": 60}, seed=0)
    assert (labels == -1).all()
    s = stability(X, "hdbscan", {"min_cluster_size": 60}, runs=3, fraction=0.8, seed=0)
    assert np.isnan(s["ari_mean"])
    assert s["clusters_in_full"] == 0


def test_dpmm_covariance_scale_changes_how_many_clusters_are_used():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(c, 1.0, (60, 2)) for c in ([0, 0], [8, 0], [0, 8])])
    narrow = cluster(X, "dpmm", {"max_components": 15, "covariance_scale": 0.02})
    wide = cluster(X, "dpmm", {"max_components": 15, "covariance_scale": 3.0})
    assert len(np.unique(narrow)) > len(np.unique(wide))
    assert len(np.unique(wide)) <= 4
