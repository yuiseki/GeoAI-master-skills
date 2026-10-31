"""The one B x H check: does the product of the bear-side and human-side scores add anything on a later year to
their additive combination?

Both meta-models are logistic regressions (C 1.0, standardised inputs) on z_B and z_H, the logits of the M_B and
M_H scores centred on their training means; the interaction model adds z_B * z_H. They are fitted on cross-fitted
scores: the training cells are put in five folds by 10 km block (blocks shuffled with seed 0, the same fold for a
cell in every training year), M_B and M_H are fitted on four folds and score the fifth. On the test year the
meta-models take the M_B and M_H scores fitted on all training years (saved by interface_models.py).

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      uvx --with numpy==2.5.4 --with scipy --with scikit-learn==1.9.1 --with pandas --with pyarrow python \
      projects/_bear/akita-bear-human-interface/scripts/interface_interaction.py artifacts/_bear/akita-bear-risk-grid-100m \
      artifacts/_bear/akita-bear-human-interface --train 2023 2024 --test 2025 --boot 1000 \
      --out projects/_bear/akita-bear-human-interface/outputs/interaction_b2.json
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

import interface_models as im
from interface_role_perm import REAL

K = 5
EPS = 1e-6


def block_folds(block, k=K, seed=0):
    u, inv = np.unique(block, return_inverse=True)
    order = np.random.default_rng(seed).permutation(len(u))
    fold_of_block = np.empty(len(u), dtype=int)
    fold_of_block[order] = np.arange(len(u)) % k
    return fold_of_block[inv]


def logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def design(sb, sh, centre, interaction):
    zb, zh = logit(sb) - centre[0], logit(sh) - centre[1]
    cols = [zb, zh, zb * zh] if interaction else [zb, zh]
    return np.column_stack(cols)


def meta_model():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))


def main():
    import model_eval as me

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("--train", type=int, nargs="+", required=True)
    a.add_argument("--test", type=int, required=True)
    a.add_argument("--boot", type=int, default=1000)
    a.add_argument("--out", type=Path, required=True)
    args = a.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists")
    t0 = time.time()
    from sklearn.ensemble import HistGradientBoostingClassifier

    hashes = im.check_inputs(args.art)
    X, names, counts, muni = im.static_matrix(args.art)
    sets = im.feature_sets(im.load_roles(im.ROLES_FILE, names), names)
    block = im.blocks_10km(args.art)
    fold = block_folds(block)
    ys = [im.labels(counts, muni, y)[0] for y in args.train]
    oof = {m: np.full(len(block), np.nan) for m in ("M_B", "M_H")}
    for k in range(K):
        tr = fold != k
        for m in oof:
            Xs = im.columns(X, names, sets[m])
            mdl = HistGradientBoostingClassifier(**me.HGB, random_state=0)
            mdl.fit(np.vstack([Xs[tr]] * len(ys)), np.concatenate([y[tr] for y in ys]))
            oof[m][~tr] = mdl.predict_proba(Xs[~tr])[:, 1]
        print(f"fold {k}: {int((~tr).sum())} cells, {time.time() - t0:.0f} s", flush=True)
    centre = (float(logit(oof["M_B"]).mean()), float(logit(oof["M_H"]).mean()))
    ytr = np.concatenate(ys)
    real_file = args.work / "scores" / REAL[tuple(args.train + [args.test])]
    z = np.load(real_file)
    test_b, test_h = z["M_B"].astype(float), z["M_H"].astype(float)
    scores, coefs = {}, {}
    for name, inter in (("stack_add", False), ("stack_mult", True)):
        mdl = meta_model().fit(np.vstack([design(oof["M_B"], oof["M_H"], centre, inter)] * len(ys)), ytr)
        scores[name] = mdl.predict_proba(design(test_b, test_h, centre, inter))[:, 1]
        coefs[name] = mdl[-1].coef_.ravel().tolist()
    scores["M_BH"] = z["M_BH"].astype(float)
    scores["M_B"], scores["M_H"] = test_b, test_h
    y, c = im.labels(counts, muni, args.test)
    res = me.evaluate(scores, y, c, block, [("stack_mult", "stack_add"), ("stack_add", "M_BH"), ("stack_mult", "M_BH")],
                      B=args.boot, seed=0)
    res["coef_standardised"] = coefs
    res["oof_centre_logit"] = centre
    res["setup"] = {"train": args.train, "test": args.test, "folds": K, "fold_seed": 0, "boot": args.boot,
                    "test_scores": real_file.name, "test_scores_sha256": im.sha256(real_file), "input_sha256": hashes,
                    "derived": "meta-model scores, not observations", "seconds": round(time.time() - t0)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for m in ("M_B", "M_H", "M_BH", "stack_add", "stack_mult"):
        print(m, {k: round(res[m][k], 4) for k in ("capture@1%", "capture@5%", "capture@10%", "ap", "auc")})
    print(json.dumps(res["diff_capture@5%"], indent=1), coefs)


if __name__ == "__main__":
    main()
