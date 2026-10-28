"""Leave-regions-out comparison of feature sources (plan of bear-risk-sources).

For a feature variant, every training set of 1, 2 or 3 of the four regions is fitted on all its cells (subsampling
negatives moved the score by 0.01-0.05, see the plan) and scored on each region outside it by capture@5% (ties broken at random,
seed 0). Rows: variant, train, k, target, capture5, n_pos.

Usage:
    ... python run_matrix.py OUT.csv VARIANT [VARIANT ...] [--check-subsample]
"""

import itertools
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../bear-risk-transfer/scripts"))
sys.path.insert(0, os.path.join(HERE, "../../../../.agents/skills/grid-risk-mapping/scripts"))
import features as ft  # noqa: E402
import score_risk_map as sr  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))
ART = {"akita": f"{ROOT}/artifacts/_bear/akita-bear-risk-grid-100m", "gifu": f"{ROOT}/artifacts/_bear/bear-risk-transfer/gifu",
       "kyoto": f"{ROOT}/artifacts/_bear/bear-risk-transfer/kyoto", "ishikawa": f"{ROOT}/artifacts/_bear/bear-risk-transfer/ishikawa"}
SRC = f"{ROOT}/artifacts/_bear/bear-risk-sources"
REGIONS = list(ART)
HGB = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=500, l2_regularization=1.0, early_stopping=False)
BLDG = ["bldg_500", "d_building"]
ROAD = ["d_road_major", "d_road", "d_track"]
RIVER = ["d_river", "d_stream"]
# variant -> (replacement file stem or None, columns to drop, add climate)
VARIANTS = {
    "base": ({}, [], False),
    "bldg_none": ({}, BLDG, False), "bldg_ovt": ({"bldg": "bldg_ovt"}, [], False),
    "road_none": ({}, ROAD, False), "road_ovt": ({"road": "road_ovt"}, [], False), "road_ksj": ({"road": "road_ksj"}, [], False),
    "river_none": ({}, RIVER, False), "river_ovt": ({"river": "river_ovt"}, [], False), "river_ksj": ({"river": "river_ksj"}, [], False),
    "clim": ({}, [], True),
    # combinations of the changes that helped one at a time (added after seeing those results)
    "combo_clim_nobldg": ({}, BLDG, True), "combo_clim_bldgovt": ({"bldg": "bldg_ovt"}, [], True),
}
CLIM = ["t_year", "t_jan", "t_aug", "snow_max", "precip_year", "sun_year", "rad_year"]


def labels(region):
    art = ART[region]
    lab = np.load(f"{art}/grid_mask.npz")["muni"] >= 0
    if region == "akita":
        r = np.load(f"{art}/reports_by_year.npz")
        total = sum(r[k] for k in r.files)
    else:
        total = np.load(f"{art}/reports.npz")["total"]
    return total[lab] > 0, lab


def design(region, variant):
    """X for the region's cells under a variant, and the column names; cached as .npy."""
    cache = f"{SRC}/{region}/X_{variant}.npy"
    names_path = f"{SRC}/{region}/X_{variant}.names"
    if os.path.exists(cache):
        return np.load(cache), open(names_path).read().split(",")
    rep, drop, clim = VARIANTS[variant]
    art = ART[region]
    wc, dem, pop = (np.load(f"{art}/{n}.npz") for n in ("worldcover", "dem", "worldpop"))
    osm = dict(np.load(f"{art}/osm.npz"))
    for block, stem in rep.items():
        osm.update(dict(np.load(f"{SRC}/{region}/{stem}.npz")))
    st = ft.static_features(wc, dem, pop, osm)
    if clim:
        g = np.load(f"{SRC}/{region}/g02.npz")
        st.update({k: g[k] for k in CLIM})
    names = [n for n in st if n not in drop]
    _, inside = labels(region)
    X = np.column_stack([st[n][inside] for n in names]).astype(np.float32)
    os.makedirs(f"{SRC}/{region}", exist_ok=True)
    np.save(cache, X)
    open(names_path, "w").write(",".join(names))
    return X, names


def subsample(y, rng, rate=0.1):
    keep = y | (rng.random(len(y)) < rate)
    w = np.where(y, 1.0, 1.0 / rate)
    return keep, w


def fit(train, variant, full=True):
    from sklearn.ensemble import HistGradientBoostingClassifier

    Xs, ys, ws = [], [], []
    for r in train:
        X, _ = design(r, variant)
        y, _ = labels(r)
        if full:
            keep, w = np.ones(len(y), bool), np.ones(len(y))
        else:
            keep, w = subsample(y, np.random.default_rng(0))
        Xs.append(X[keep]), ys.append(y[keep]), ws.append(w[keep])
    m = HistGradientBoostingClassifier(**HGB, random_state=0)
    m.fit(np.vstack(Xs), np.concatenate(ys), sample_weight=np.concatenate(ws))
    return m


def capture5(model, region, variant):
    X, _ = design(region, variant)
    y, _ = labels(region)
    s = model.predict_proba(X)[:, 1]
    return sr.capture(sr.rank_order(s, seed=0), y, 0.05), int(y.sum())


def main():
    import pandas as pd

    out = sys.argv[1]
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    if "--check-subsample" in sys.argv:
        for full in (True, False):
            m = fit(["akita"], "base", full=full)
            print("akita -> gifu, base,", "all cells" if full else "10% negatives", capture5(m, "gifu", "base"))
        return
    done = pd.read_csv(out) if os.path.exists(out) else pd.DataFrame(columns=["variant", "train", "k", "target", "capture5", "n_pos"])
    for variant in args:
        rows = []
        for k in (1, 2, 3):
            for train in itertools.combinations(REGIONS, k):
                key = "+".join(train)
                if ((done.variant == variant) & (done.train == key)).any():
                    continue
                m = fit(train, variant)
                for t in REGIONS:
                    if t in train:
                        continue
                    c, n = capture5(m, t, variant)
                    rows.append({"variant": variant, "train": key, "k": k, "target": t, "capture5": c, "n_pos": n})
                print(variant, key, [round(r["capture5"], 3) for r in rows if r["train"] == key], flush=True)
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
        done.to_csv(out, index=False)
    print(done.groupby(["variant", "k"]).capture5.mean().unstack().round(3))


if __name__ == "__main__":
    main()
