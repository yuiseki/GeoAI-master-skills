"""Move the Akita environment model (B_env) to other regions and score it against local baselines.

1. Fit B_env on Akita exactly as in the Akita project (static features, bear years 2023-2025 stacked, the same
   gradient boosting settings, seed 0) and check that its Akita scores equal the saved ones.
2. For each region: AK = the Akita model's score per cell; B_pop = people within about 500 m (second key: 2 km);
   LOCAL = the same model fitted on the region's own labels, scored by 5-fold cross-validation over 10 km blocks.
3. Write one Parquet per region (cell, ix, iy, block, label, AK, B_pop, B_pop2, LOCAL) for score_risk_map.py,
   and a CSV of feature quantiles (Akita against each region).

Usage:
    uvx --with numpy --with scipy --with scikit-learn --with pandas --with pyarrow python transfer_eval.py \\
        AKITA_ART AKITA_B3_SCORES.npz OUT_DIR REGION_ART [REGION_ART ...]
"""

import os
import sys

import numpy as np

import features as ft

HGB = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=500, l2_regularization=1.0, early_stopping=False)


def static_table(art):
    wc, dem, pop, osm = (np.load(f"{art}/{n}.npz") for n in ("worldcover", "dem", "worldpop", "osm"))
    st = ft.static_features(wc, dem, pop, osm)
    lab = np.load(f"{art}/grid_mask.npz")["muni"]
    inside = lab >= 0
    names = list(st)
    return np.column_stack([st[n][inside] for n in names]).astype(np.float32), names, inside


def block_folds(blocks, folds, seed=0):
    ids = np.unique(blocks)
    perm = np.random.default_rng(seed).permutation(len(ids))
    fold_of = dict(zip(ids[perm], np.arange(len(ids)) % folds))
    return np.array([fold_of[b] for b in blocks])


def local_cv(X, y, blocks, folds=5, seed=0, params=None):
    from sklearn.ensemble import HistGradientBoostingClassifier

    f = block_folds(blocks, folds, seed)
    p = np.full(len(y), np.nan)
    for k in range(folds):
        m = HistGradientBoostingClassifier(**(params or HGB), random_state=seed)
        m.fit(X[f != k], y[f != k])
        p[f == k] = m.predict_proba(X[f == k])[:, 1]
    return p


def main():
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingClassifier

    akita, b3_scores, out = sys.argv[1], sys.argv[2], sys.argv[3]
    regions = sys.argv[4:]
    Xa, names, inside_a = static_table(akita)
    rep = np.load(f"{akita}/reports_by_year.npz")
    ya = np.concatenate([(rep[f"c{y}"][inside_a] > 0) for y in (2023, 2024, 2025)])
    model = HistGradientBoostingClassifier(**HGB, random_state=0)
    model.fit(np.vstack([Xa] * 3), ya)
    pa = model.predict_proba(Xa)[:, 1]
    saved = np.load(b3_scores)["B_env"]
    print(f"Akita refit: max |score - saved B_env| = {np.abs(pa.astype(np.float32) - saved).max():.2e} over {len(pa)} cells")
    if not np.allclose(pa.astype(np.float32), saved, atol=1e-6):
        raise SystemExit("the refit does not reproduce the Akita model")
    quant = []
    qcols = ["tree", "crop", "built", "pop_500", "bldg_500", "d_building", "d_road", "elev", "forest_edge"]
    for n in qcols:
        v = Xa[:, names.index(n)]
        quant.append({"region": "akita", "feature": n, **{f"q{q}": float(np.nanpercentile(v, q)) for q in (10, 50, 90)}})
    for art in regions:
        region = os.path.basename(art.rstrip("/"))
        X, n2, inside = static_table(art)
        if n2 != names:
            raise SystemExit(f"{region}: the features differ from Akita's")
        cells = pd.read_parquet(f"{art}/cells.parquet", columns=["cell", "ix", "iy"])
        label = np.load(f"{art}/reports.npz")["total"][inside]
        blocks = (cells.ix.to_numpy() // 100) * 100000 + cells.iy.to_numpy() // 100
        tab = pd.DataFrame({"cell": cells.cell, "ix": cells.ix, "iy": cells.iy, "block": blocks, "label": label,
                            "AK": model.predict_proba(X)[:, 1], "B_pop": X[:, names.index("pop_500")],
                            "B_pop2": X[:, names.index("pop_2000")]})
        tab["LOCAL"] = local_cv(X, label > 0, blocks)
        for p in sorted(k for k in np.load(f"{art}/reports.npz").files if k.startswith("p")):
            tab[f"label_{p}"] = np.load(f"{art}/reports.npz")[p][inside]
        tab.to_parquet(f"{out}/{region}_table.parquet")
        print(f"{region}: {len(tab)} cells, positive {int((label > 0).sum())}, blocks {len(np.unique(blocks))}")
        for n in qcols:
            v = X[:, names.index(n)]
            quant.append({"region": region, "feature": n, **{f"q{q}": float(np.nanpercentile(v, q)) for q in (10, 50, 90)}})
    pd.DataFrame(quant).to_csv(f"{out}/feature_quantiles.csv", index=False)


if __name__ == "__main__":
    main()
