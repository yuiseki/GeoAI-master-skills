"""B_env split by feature role: the same gradient boosting on the bear-side (B), human-side (H) and interface (I)
features of feature_roles.csv and their unions, scored on a later bear year, next to the saved B_env (M_FULL).

Nothing about the model changes but its columns: the HGB settings, seed, labels (one or more reports in the bear
year), cells and training years are those of akita-bear-risk-grid-100m/scripts/model_eval.py. The features are
static, so a model gives every cell one score whatever the year; the training rows are the cells stacked once per
training year, in the same order as model_eval.design, so 28 columns reproduce the saved B_env exactly.

From repository root:
    P=projects/_bear/akita-bear-human-interface/scripts; A=artifacts/_bear/akita-bear-risk-grid-100m
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts uvx --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pandas --with pyarrow python $P/interface_models.py $A \
      --train 2023 --test 2024 --boot 500 --saved $A/eval/b1_dev_2023_to_2024_scores.npz --check-full \
      --out projects/_bear/akita-bear-human-interface/outputs/b1_dev_2023_to_2024.json \
      --scores artifacts/_bear/akita-bear-human-interface/scores/b1_dev_2023_to_2024.npz
    # axes only (M_B and M_H, no evaluation), for the phase space:
    ... $P/interface_models.py $A --train 2025 2026 --axes-only --scores .../scores/axes_2025-2026.npz
"""

import argparse
import csv
import hashlib
import json
import time
from itertools import permutations
from math import factorial
from pathlib import Path

import numpy as np

ROLES_FILE = Path(__file__).resolve().parents[1] / "feature_roles.csv"
ROLE_NAMES = ("B", "H", "I", "X")
UNIONS = {"M_B": "B", "M_H": "H", "M_I": "I", "M_BH": "BH", "M_BI": "BI", "M_HI": "HI", "M_BHI": "BHI"}
MAIN = ("M_B", "M_H", "M_BH", "M_BHI")
SAVED_SHA = {  # the B_env score files of akita-bear-risk-grid-100m
    "b1_dev_2023_to_2024_scores.npz": "743c73ac48d77169f3348971358e45b7cffd0dca58dba5ff1617929fb732404b",
    "b2_confirm_2023-2024_to_2025_scores.npz": "aa33ceeb78d8ff46cd39388f8884b1d1b20547d163d235ddb65ac74831be82ba",
    "b3_confirm_2023-2025_to_2026_scores.npz": "9895dbd7b6e89a304a072b92543a5b39088b4363b99b44cf46dcb1d1727460f5",
}
INPUT_SHA = {
    "grid.json": "6ddd6f85dceb4bed84ddb1dfbe43c3fe69110ff54f852f1da68bf6bb78336523",
    "grid_mask.npz": "acaa98d8fd8ba20819772fcc1635e9c263af23c0f0e6c82bb57057d8c5bddf24",
    "cells.parquet": "8a86f502d86ca6cedc0ab7e9d4a14fa8a28b9e3e11213bbbc6bf077cae9e14fa",
    "worldcover.npz": "2d5601b2c672657134270d517464bd56e85aa1d1f563626384a74961c3d20009",
    "dem.npz": "d40bda548be312c7087180f61b68f9fa76fa8a97b37f8a9a5bf6304f6708742b",
    "worldpop.npz": "49dbc2ea5c8f7c27db3256d6dd185e5ef7b76fa37cdfaea817b1151d563958d2",
    "osm.npz": "9ee83730a5d3d815747690ee8d8587a07dd6bf052e66812fe51cfd5d81520282",
    "reports_by_year.npz": "b7f5d77e9e263dd0761a088c6e8b0259f4f67ef1a6497e9c093699e2dcb015a4",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_inputs(art):
    got = {k: sha256(Path(art) / k) for k in INPUT_SHA}
    bad = [k for k in INPUT_SHA if got[k] != INPUT_SHA[k]]
    if bad:
        raise ValueError(f"fixed inputs changed: {bad}")
    return got


def load_roles(path, static_names):
    """role -> features, each list in the order of static_names. Every static feature exactly once."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    feats = [r["feature"] for r in rows]
    if len(set(feats)) != len(feats):
        raise ValueError("a feature is listed twice")
    if sorted(feats) != sorted(static_names):
        raise ValueError(f"roles do not cover the static features: {set(static_names) ^ set(feats)}")
    role = {r["feature"]: r["role"] for r in rows}
    if not set(role.values()) <= set(ROLE_NAMES):
        raise ValueError(f"unknown role: {set(role.values()) - set(ROLE_NAMES)}")
    return {k: [f for f in static_names if role[f] == k] for k in ROLE_NAMES}


def feature_sets(roles, static_names):
    """Model name -> its columns (in static order), for every union of B, H and I."""
    return {m: [f for f in static_names if any(f in roles[g] for g in groups)] for m, groups in UNIONS.items()}


def columns(X, names, wanted):
    return X[:, [names.index(w) for w in wanted]]


def skill_share(cap, cap_full, base=0.05):
    """Share of the full model's lift over a random choice (capture@5% of a random map is 0.05)."""
    return (cap - base) / (cap_full - base)


def shapley3(caps, base=0.05):
    """Shapley values of the groups B, H and I for capture, from the seven subset models (empty set = base).

    caps: {"B", "H", "I", "BH", "BI", "HI", "BHI"} -> capture."""
    def v(s):
        key = "".join(g for g in "BHI" if g in s)
        return base if not key else caps[key]
    phi = {g: 0.0 for g in "BHI"}
    for order in permutations("BHI"):
        seen = set()
        for g in order:
            phi[g] += v(seen | {g}) - v(seen)
            seen.add(g)
    return {g: p / factorial(3) for g, p in phi.items()}


def static_matrix(art):
    import model_eval as me

    static, counts, muni = me.load(art)
    X, names, _, _ = me.design(static, counts, muni, min(counts), history=False)
    return X, names, counts, muni


def labels(counts, muni, year):
    c = counts[year][muni >= 0]
    return c > 0, c


def fit_scores(X, names, counts, muni, train_years, models, seed=0):
    """Score per prefecture cell for each model, fitted on the cells stacked once per training year."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    import model_eval as me

    ytr = np.concatenate([labels(counts, muni, y)[0] for y in train_years])
    out = {}
    for m, cols in models.items():
        Xs = columns(X, names, cols)
        Xtr = np.vstack([Xs] * len(train_years))
        t0 = time.time()
        mdl = HistGradientBoostingClassifier(**me.HGB, random_state=seed).fit(Xtr, ytr)
        out[m] = mdl.predict_proba(Xs)[:, 1]
        print(f"  {m}: {len(cols)} features, {time.time() - t0:.0f} s", flush=True)
    return out


def blocks_10km(art):
    import pandas as pd

    cells = pd.read_parquet(Path(art) / "cells.parquet", columns=["ix", "iy"])
    return (cells.ix.to_numpy() // 100) * 10000 + cells.iy.to_numpy() // 100


COMPARE = [("M_B", "M_H"), ("M_BH", "M_B"), ("M_BH", "M_H"), ("M_BHI", "M_BH"), ("M_FULL", "M_BHI"),
           ("M_FULL", "M_BH"), ("M_FULL", "M_B"), ("M_FULL", "M_H")]


def main():
    import scipy
    import sklearn

    import model_eval as me

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("--train", type=int, nargs="+", required=True)
    a.add_argument("--test", type=int)
    a.add_argument("--boot", type=int, default=1000)
    a.add_argument("--saved", type=Path, help="the saved B_env score file of the same split")
    a.add_argument("--check-full", action="store_true", help="refit all 28 features and compare with --saved")
    a.add_argument("--axes-only", action="store_true", help="fit M_B and M_H only, no evaluation")
    a.add_argument("--out", type=Path)
    a.add_argument("--scores", type=Path, required=True)
    args = a.parse_args()
    for p in (args.out, args.scores):
        if p is not None and p.exists():
            raise SystemExit(f"{p} exists; refusing to overwrite a result")
    t0 = time.time()
    hashes = check_inputs(args.art)
    X, names, counts, muni = static_matrix(args.art)
    roles = load_roles(ROLES_FILE, names)
    sets = feature_sets(roles, names)
    if args.axes_only:
        scores = fit_scores(X, names, counts, muni, args.train, {m: sets[m] for m in ("M_B", "M_H")})
        args.scores.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.scores, **{k: v.astype(np.float32) for k, v in scores.items()})
        print("wrote", args.scores, round(time.time() - t0), "s")
        return
    if args.test is None or args.saved is None or max(args.train) >= args.test:
        raise SystemExit("--test after the training years and --saved are required")
    if SAVED_SHA.get(args.saved.name) != sha256(args.saved):
        raise SystemExit(f"{args.saved} is not the fixed saved B_env")
    full = np.load(args.saved)["B_env"].astype(float)
    check = None
    if args.check_full:
        refit = fit_scores(X, names, counts, muni, args.train, {"B_env": names})["B_env"]
        d = float(np.max(np.abs(refit.astype(np.float32).astype(float) - full)))
        check = {"max_abs_diff": d, "ok": d <= 1e-6}
        print("refit of all 28 features vs saved B_env: max abs diff", d, flush=True)
        if not check["ok"]:
            raise SystemExit("the refit does not reproduce the saved B_env; stopping")
    scores = fit_scores(X, names, counts, muni, args.train, sets)
    scores["M_FULL"] = full
    y, c = labels(counts, muni, args.test)
    res = me.evaluate(scores, y, c, blocks_10km(args.art), COMPARE, B=args.boot, seed=0)
    cap = {m: res[m]["capture@5%"] for m in scores}
    res["skill_share_of_full"] = {m: skill_share(cap[m], cap["M_FULL"]) for m in scores if m != "M_FULL"}
    res["shapley_capture@5%"] = shapley3({UNIONS[m]: cap[m] for m in UNIONS})
    res["shapley_capture@5%"]["X (M_FULL - M_BHI)"] = cap["M_FULL"] - cap["M_BHI"]
    res["setup"] = {"train": args.train, "test": args.test, "boot": args.boot, "seed": 0, "hgb": me.HGB,
                    "feature_sets": sets, "roles_file_sha256": sha256(ROLES_FILE), "input_sha256": hashes,
                    "saved_b_env": {"file": args.saved.name, "sha256": SAVED_SHA[args.saved.name]},
                    "refit_check": check, "versions": {"numpy": np.__version__, "scipy": scipy.__version__,
                                                       "scikit-learn": sklearn.__version__},
                    "derived": "scores are model predictions, not observations", "seconds": round(time.time() - t0)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.scores.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    np.savez_compressed(args.scores, **{k: v.astype(np.float32) for k, v in scores.items() if k != "M_FULL"})
    for m in ("M_B", "M_H", "M_I", "M_BI", "M_HI", "M_BH", "M_BHI", "M_FULL"):
        print(m, {k: round(res[m][k], 4) for k in ("capture@1%", "capture@5%", "capture@10%", "ap", "auc")})
    print(json.dumps(res["diff_capture@5%"], indent=1))


if __name__ == "__main__":
    main()
