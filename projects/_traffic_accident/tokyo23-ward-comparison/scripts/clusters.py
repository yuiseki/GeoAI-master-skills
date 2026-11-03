"""Read the clustering skill's labels (README), apply the rule of EXPERIMENT_PLAN C5, and describe the groups.

Run from the repository root after cluster_units.py has written labels-kmeans.parquet and labels-ward.parquet:
env -u PYTHONPATH uvx --with duckdb --with scikit-learn --with numpy python projects/_traffic_accident/tokyo23-ward-comparison/scripts/clusters.py

A setting gets group names only if its stability ARI is 0.6 or more for both methods and the two methods agree
(ARI 0.6 or more). Stabilities are read from the skill's printed output (outputs/clusters-*.txt).
Writes outputs/clusters.json and outputs/clusters.csv (the groups of the settings that pass).
"""

import csv
import json
import re
from pathlib import Path

import duckdb
import numpy as np
from sklearn.metrics import adjusted_rand_score

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
ART = ROOT / "artifacts/_traffic_accident" / PROJECT.name
OUT = PROJECT / "outputs"
RULE = 0.6
KS = (2, 3, 4, 5, 6)


def stabilities(text):
    """k -> stability ARI from the skill's printed lines ('k=3  clusters 3, ... stability ARI 0.559 ...')."""
    return {int(k): float(v) for k, v in re.findall(r"^k=(\d+)\s.*?stability ARI ([0-9.]+)", text, re.MULTILINE)}


def passes(stab_a, stab_b, agreement, rule=RULE):
    return stab_a >= rule and stab_b >= rule and agreement >= rule


def principal_components(z, n=2):
    """Explained shares, loadings and scores of the first n principal components of the standardised matrix z
    (rows units, columns features). The sign of each component makes its largest loading positive."""
    z = np.asarray(z, dtype=float)
    u, sv, vt = np.linalg.svd(z - z.mean(axis=0), full_matrices=False)
    explained = sv ** 2 / (sv ** 2).sum()
    for i in range(n):
        if vt[i, np.argmax(np.abs(vt[i]))] < 0:
            vt[i], u[:, i] = -vt[i], -u[:, i]
    return explained[:n], vt[:n], (u[:, :n] * sv[:n])


def main():
    labels = {m: {r[0]: r[1:] for r in duckdb.sql(f"select * from '{ART / f'labels-{m}.parquet'}' order by id").fetchall()}
              for m in ("kmeans", "ward")}
    cols = {m: [c for c in duckdb.sql(f"select * from '{ART / f'labels-{m}.parquet'}' limit 0").columns if c != "id"]
            for m in labels}
    stab = {m: stabilities((OUT / f"clusters-{m}.txt").read_text(encoding="utf-8")) for m in labels}
    with (OUT / "wards.csv").open(encoding="utf-8") as f:
        wards = {r["code"]: r for r in csv.DictReader(f)}
    codes = sorted(wards)
    settings = {}
    for k in KS:
        a = np.array([labels["kmeans"][c][cols["kmeans"].index(f"k={k}")] for c in codes])
        b = np.array([labels["ward"][c][cols["ward"].index(f"k={k}")] for c in codes])
        agree = float(adjusted_rand_score(a, b))
        settings[k] = {"stability_kmeans": stab["kmeans"][k], "stability_ward": stab["ward"][k],
                       "kmeans_vs_ward_ari": round(agree, 3),
                       "passes": passes(stab["kmeans"][k], stab["ward"][k], agree), "labels_kmeans": a.tolist()}
    features = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))["settings"]["features"]
    groups, rows = {}, []
    for k, s in settings.items():
        if not s["passes"]:
            continue
        for g in sorted(set(s["labels_kmeans"])):
            members = [c for c, lab in zip(codes, s["labels_kmeans"]) if lab == g]
            groups[f"k={k} group {g}"] = {
                "size": len(members), "wards": [wards[c]["name"] for c in members],
                "mean": {f: round(float(np.mean([float(wards[c][f]) for c in members])), 4) for f in features},
                "others_mean": {f: round(float(np.mean([float(wards[c][f]) for c in codes if c not in members])), 4)
                                for f in features}}
            rows += [{"k": k, "group": g, "code": c, "name": wards[c]["name"],
                      "known_division": wards[c]["known_division"]} for c in members]
    (OUT / "clusters.json").write_text(json.dumps({"rule": f"stability ARI >= {RULE} for k-means and Ward, and "
                                                           f"k-means vs Ward ARI >= {RULE}",
                                                   "settings": settings, "groups": groups},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    if rows:
        with (OUT / "clusters.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    # Principal components of the 12 standardised shares (added after the clustering: R005), to describe how the
    # wards differ when no grouping beyond two is stable.
    with (OUT / "features_z.csv").open(encoding="utf-8") as f:
        zrows = {r["code"]: r for r in csv.DictReader(f)}
    z = [[float(zrows[c][f]) for f in features] for c in codes]
    explained, loadings, scores = principal_components(z)
    (OUT / "pca.json").write_text(json.dumps({
        "features": features, "explained": [round(float(e), 3) for e in explained],
        "loadings": [{f: round(float(v), 3) for f, v in zip(features, row)} for row in loadings],
        "scores": {c: [round(float(v), 3) for v in scores[i]] for i, c in enumerate(codes)}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    for k, s in settings.items():
        print(k, {x: s[x] for x in ("stability_kmeans", "stability_ward", "kmeans_vs_ward_ari", "passes")})
    print(json.dumps(groups, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
