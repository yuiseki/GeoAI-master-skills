"""Cluster units on their features, and check what the clusters are worth.

Features are standardised (mean 0, sd 1) before clustering. For each method and setting it reports:
    clusters, noise    number of clusters and of units left as noise (density methods)
    silhouette         separation of the clusters in feature space (noise left out)
    stability          mean adjusted Rand index between the clustering of all units and the
                       clusterings of random subsets (--fraction of the units), on the units each
                       subset saw. Near 1: the same clusters come back; near 0: they do not.
    external ARI       with --compare-with, agreement with a known grouping (regions, income groups)
    spatial cohesion   with --lon/--lat, share of each unit's k nearest units (great-circle) that are
                       in its cluster, against the share expected when labels are shuffled

Methods and settings (one or more, comma-separated values):
    kmeans   --k 3,4,5
    hdbscan  --min-cluster-size 5,10
    dbscan   --eps 0.5 --min-samples 5        (eps in standardised units)
    dpmm     --max-components 10              (Bayesian Gaussian mixture, Dirichlet process prior)

Usage:
    uvx --with duckdb --with scikit-learn --with pyarrow python cluster_units.py TABLE ID FEATURE [...] \
        --method kmeans --k 3,4,5,6 [--compare-with COL ...] [--lon COL --lat COL] \
        [--runs 20] [--fraction 0.8] [--labels-out labels.parquet]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import DBSCAN, HDBSCAN, KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import BayesianGaussianMixture
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "spatial-autocorrelation" / "scripts"))
from spatial_autocorrelation import knn_neighbors  # noqa: E402


def cluster(X, method, params, seed=0):
    """Labels per row; -1 is noise. X is standardised here."""
    Z = StandardScaler().fit_transform(np.asarray(X, float))
    if method == "kmeans":
        return KMeans(n_clusters=params["k"], n_init=10, random_state=seed).fit_predict(Z)
    if method == "hdbscan":
        return HDBSCAN(min_cluster_size=params["min_cluster_size"], copy=True).fit_predict(Z)
    if method == "dbscan":
        return DBSCAN(eps=params["eps"], min_samples=params["min_samples"]).fit_predict(Z)
    if method == "dpmm":
        m = BayesianGaussianMixture(
            n_components=params["max_components"],
            weight_concentration_prior_type="dirichlet_process",
            max_iter=1000, random_state=seed).fit(Z)
        labels = m.predict(Z)
        # Renumber the components actually used as 0..n-1.
        return np.unique(labels, return_inverse=True)[1]
    raise SystemExit(f"unknown method {method}")


def stability(X, method, params, runs=20, fraction=0.8, seed=0):
    X = np.asarray(X, float)
    n = len(X)
    full = cluster(X, method, params, seed)
    m = int(round(fraction * n))
    found = len(np.unique(full[full >= 0]))
    if found < 2:
        # With fewer than two clusters every run agrees trivially; that is not stability.
        return {"ari_mean": float("nan"), "ari_sd": float("nan"), "units_per_run": m,
                "clusters_in_full": found}
    rng = np.random.default_rng(seed)
    aris = []
    for r in range(runs):
        sub = np.sort(rng.choice(n, size=m, replace=False))
        labels = cluster(X[sub], method, params, seed + 1 + r)
        aris.append(adjusted_rand_score(full[sub], labels))
    return {"ari_mean": float(np.mean(aris)), "ari_sd": float(np.std(aris)), "units_per_run": m,
            "clusters_in_full": found}


def external_agreement(labels, known):
    return float(adjusted_rand_score(np.asarray(known), np.asarray(labels)))


def spatial_cohesion(labels, lon, lat, k=6, permutations=999, seed=0):
    labels = np.asarray(labels)
    nb = np.array([row for row in knn_neighbors(lon, lat, k)])

    def share(lab):
        return float((lab[nb] == lab[:, None]).mean())

    observed = share(labels)
    rng = np.random.default_rng(seed)
    sim = np.array([share(rng.permutation(labels)) for _ in range(permutations)])
    p = (int((sim >= observed).sum()) + 1) / (permutations + 1)
    return {"same_share": observed, "expected_share": float(sim.mean()), "p_sim": p}


def settings(a):
    def nums(s, cast):
        return [cast(v) for v in s.split(",")]
    if a.method == "kmeans":
        return [{"k": v} for v in nums(a.k, int)]
    if a.method == "hdbscan":
        return [{"min_cluster_size": v} for v in nums(a.min_cluster_size, int)]
    if a.method == "dbscan":
        return [{"eps": e, "min_samples": m} for e in nums(a.eps, float)
                for m in nums(a.min_samples, int)]
    return [{"max_components": v} for v in nums(a.max_components, int)]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("features", nargs="+")
    p.add_argument("--method", choices=["kmeans", "hdbscan", "dbscan", "dpmm"], required=True)
    p.add_argument("--k", default="3,4,5,6")
    p.add_argument("--min-cluster-size", default="5,10")
    p.add_argument("--eps", default="0.5")
    p.add_argument("--min-samples", default="5")
    p.add_argument("--max-components", default="10")
    p.add_argument("--compare-with", nargs="*", default=[])
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--neighbors", type=int, default=6)
    p.add_argument("--runs", type=int, default=20)
    p.add_argument("--fraction", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--labels-out")
    a = p.parse_args()

    import duckdb

    extra = list(a.compare_with) + ([a.lon, a.lat] if a.lon else [])
    cols = [a.id, *a.features, *extra]
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols)
                      + f" from '{a.table}'").fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("some rows have a missing value; drop them first")
    nf = len(a.features)
    ids = [r[0] for r in rows]
    X = np.array([r[1:1 + nf] for r in rows], float)
    known = {c: np.array([r[1 + nf + i] for r in rows]) for i, c in enumerate(a.compare_with)}
    if a.lon:
        lon = np.array([r[-2] for r in rows], float)
        lat = np.array([r[-1] for r in rows], float)
    print(f"units: {len(ids)}, features: {a.features} (standardised), method: {a.method}")

    out_labels = {}
    for params in settings(a):
        labels = cluster(X, a.method, params, a.seed)
        name = ",".join(f"{k}={v}" for k, v in params.items())
        out_labels[name] = labels
        keep = labels >= 0
        n_clusters = len(np.unique(labels[keep]))
        if n_clusters < 2:
            print(f"{name:<22} clusters {n_clusters}, noise {int((~keep).sum())}: no clustering found;"
                  " stability, agreement and cohesion are not measured")
            continue
        sil = (silhouette_score(StandardScaler().fit_transform(X)[keep], labels[keep])
               if 1 < n_clusters < keep.sum() else float("nan"))
        st = stability(X, a.method, params, a.runs, a.fraction, a.seed)
        line = (f"{name:<22} clusters {n_clusters}, noise {int((~keep).sum())}, "
                f"silhouette {sil:.3f}, stability ARI {st['ari_mean']:.3f} (sd {st['ari_sd']:.3f})")
        for c, v in known.items():
            line += f", ARI vs {c} {external_agreement(labels, v):.3f}"
        if a.lon:
            sc = spatial_cohesion(labels, lon, lat, a.neighbors, 999, a.seed)
            line += (f", same cluster among {a.neighbors} nearest {sc['same_share']:.2f}"
                     f" (shuffled {sc['expected_share']:.2f}, p {sc['p_sim']:.3f})")
        print(line)
        sizes = np.unique(labels, return_counts=True)
        print("    sizes: " + ", ".join(f"{int(c)}:{int(s)}" for c, s in zip(*sizes)))

    if a.labels_out:
        import pyarrow as pa

        cols = {"id": [str(i) for i in ids]}
        cols.update({k: v.astype(int) for k, v in out_labels.items()})
        lab = pa.table(cols)
        duckdb.sql(f"copy (select * from lab order by id) to '{a.labels_out}' (format parquet)")
        print(f"labels: {a.labels_out}")


if __name__ == "__main__":
    main()
