"""Cross-fit B_env scores for the beta fit (post-hoc diagnostic, EXPERIMENT_PLAN_CROSSFIT.md).

For each training year of a target, B_env is refitted with akita-bear-risk-grid-100m's own model_eval.run_models
(same 28 static features, HistGradientBoostingClassifier, hyperparameters, labels, cells, seed 0) on the other
training years only. The static features give one score per cell. Writes ART/crossfit_benv_scores.npz and
OUT_JSON with the reproduction check against the saved b1 and b2 surfaces and the per-year sanity checks.

    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-mast-exposure/scripts \
      uvx --with numpy==2.5.4 --with scipy --with scikit-learn==1.9.1 --with pandas --with pyarrow \
      python crossfit.py BEAR_ART ART OUT_JSON
"""

import json
import os
import sys

import numpy as np

BETA_YEARS = {2025: [2023, 2024], 2026: [2023, 2024, 2025]}
OOF = {t: {y: tuple(x for x in ys if x != y) for y in ys} for t, ys in BETA_YEARS.items()}
SAVED = {(2023,): "b1_dev_2023_to_2024", (2023, 2024): "b2_confirm_2023-2024_to_2025"}
IN_SAMPLE = {2025: "b2_confirm_2023-2024_to_2025", 2026: "b3_confirm_2023-2025_to_2026"}


def fit_sets():
    return sorted({tr for t in OOF.values() for tr in t.values()})


def key(train):
    return "train_" + "_".join(map(str, train))


def pattern(diffs, fits, orig_abs_beta):
    """The reading fixed in EXPERIMENT_PLAN_CROSSFIT.md (retrospective): C, B or A."""
    if all(d["diff"] > 0 and d["lo90"] > 0 for d in diffs.values()):
        return "C"
    if any(abs(f["beta"]) / f["se_beta"] >= 1.96 and abs(f["beta"]) >= 3 * orig_abs_beta[t] for t, f in fits.items()):
        return "B"
    return "A"


def summary(s, c):
    import metrics as mt
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = c > 0
    q = lambda v: {"q10": float(np.quantile(v, 0.1)), "median": float(np.median(v)), "q90": float(np.quantile(v, 0.9)), "mean": float(v.mean())}  # noqa: E731
    return {"capture@5%": mt.capture(mt.rank_order(s), y, 0.05), "auc": float(roc_auc_score(y, s)),
            "ap": float(average_precision_score(y, s)), "pos": q(s[y]), "neg": q(s[~y]), "n_pos": int(y.sum())}


def main():
    from scipy.stats import spearmanr

    import data
    import model_eval as me

    bear, art, out = sys.argv[1:4]
    npz = f"{art}/crossfit_benv_scores.npz"
    static, counts, muni = me.load(bear)
    res = {"features": sorted(static), "n_features": len(static), "hgb": me.HGB, "fits": {}}
    if os.path.exists(npz):
        raise SystemExit(f"{npz} exists")
    scores = {}
    for tr in fit_sets():
        s = me.run_models(static, counts, muni, list(tr), max(tr) + 1, ["B_env"], seed=0)["B_env"].astype(np.float32)
        scores[key(tr)] = s
        r = {"train": list(tr)}
        if tr in SAVED:
            saved = np.load(f"{bear}/eval/{SAVED[tr]}_scores.npz")["B_env"]
            r["reproduces"] = SAVED[tr]
            r["max_abs_diff_vs_saved"] = float(np.abs(saved.astype(float) - s.astype(float)).max())
            r["identical"] = bool(np.array_equal(saved, s))
        res["fits"][key(tr)] = r
        print(tr, r, flush=True)
    np.savez_compressed(npz, **scores)
    res["scores_npz_sha256"] = data.sha256(npz)
    cnt = {t: data.vec(counts[t], muni) for t in counts}  # same cell order as the saved scores
    res["sanity"] = {}
    for target, years in OOF.items():
        ins = np.load(f"{bear}/eval/{IN_SAMPLE[target]}_scores.npz")["B_env"].astype(float)
        rows = {}
        for y, tr in years.items():
            oof = scores[key(tr)].astype(float)
            a, b = summary(ins, cnt[y]), summary(oof, cnt[y])
            rows[y] = {"in_sample": a | {"surface": IN_SAMPLE[target]}, "cross_fit": b | {"train": list(tr)},
                       "spearman_in_vs_cross": float(spearmanr(ins, oof).statistic),
                       "in_minus_cross": {k: a[k] - b[k] for k in ("capture@5%", "auc", "ap")}}
        res["sanity"][target] = rows
    if not all(r.get("identical", True) or r["max_abs_diff_vs_saved"] < 1e-6 for r in res["fits"].values()):
        res["stop"] = "the refit does not reproduce the saved B_env"
    json.dump(res, open(out, "w"), indent=1)
    for t, rows in res["sanity"].items():
        for y, r in rows.items():
            print(t, y, {k: round(v, 4) for k, v in r["in_minus_cross"].items()}, round(r["spearman_in_vs_cross"], 4),
                  round(r["in_sample"]["capture@5%"], 4), round(r["cross_fit"]["capture@5%"], 4))
    if "stop" in res:
        raise SystemExit(res["stop"])


if __name__ == "__main__":
    main()
