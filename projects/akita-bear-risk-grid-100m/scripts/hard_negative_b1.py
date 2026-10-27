"""Isolated hard-negative mining for B_env on B1 (2023 train, 2024 test).

Usage from the repository root:
    uvx --with numpy --with scipy --with scikit-learn python \
      projects/akita-bear-risk-grid-100m/scripts/hard_negative_b1.py ART_DIR \
      projects/akita-bear-risk-grid-100m/outputs/b1_hard_negative_mining.json

No sample weights, new features, future-year labels, or new HGB settings are used.
The baseline must reproduce the existing unweighted capture@5% before mining.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import metrics as mt
import model_eval as me

BASELINE_CAPTURE = 0.5341823056300268
SETTINGS = (("HN1", 10_000), ("HN3", 30_000), ("HN10", 100_000))
METRICS = ("capture@1%", "capture@5%", "capture@10%", "auc", "ap")
INPUTS = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz",
          "reports_by_year.npz", "grid_mask.npz")


def load_b1(art):
    """Reuse existing static-feature builder, but read only B1 label arrays."""
    with np.load(art / "worldcover.npz") as wc, np.load(art / "dem.npz") as dem, \
            np.load(art / "worldpop.npz") as pop, np.load(art / "osm.npz") as osm:
        static = me.ft.static_features(wc, dem, pop, osm)
    with np.load(art / "reports_by_year.npz") as reports:
        counts = {year: reports[f"c{year}"].astype(float) for year in (2023, 2024)}
    with np.load(art / "grid_mask.npz") as grid:
        muni = grid["muni"]
    return static, counts, muni


def select_indices(y, train_scores, n_hard, seed=0):
    """Keep all positives; select top-scored negatives and disjoint random negatives."""
    y = np.asarray(y, dtype=bool)
    train_scores = np.asarray(train_scores)
    if y.ndim != 1 or train_scores.shape != y.shape or n_hard <= 0:
        raise ValueError("labels/scores must be aligned 1D arrays and n_hard > 0")
    positive = np.flatnonzero(y)
    negative = np.flatnonzero(~y)
    if 2 * n_hard > len(negative):
        raise ValueError("twice n_hard exceeds the available negative cells")
    hard = negative[mt.rank_order(train_scores[negative], seed=seed)[:n_hard]]
    remaining = np.setdiff1d(negative, hard, assume_unique=True)
    random = np.random.default_rng(seed).choice(remaining, n_hard, replace=False)
    selected = np.concatenate((positive, hard, random))
    assert len(np.unique(selected)) == len(selected)
    return selected, hard, random


def fit_model(X, y):
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(**me.HGB, random_state=0)
    model.fit(X, y)  # Deliberately no sample_weight, including all-one weights.
    return model


def _metrics(scores, y, counts):
    evaluated = me.evaluate({"B_env": scores}, y, counts, np.empty(0), [], B=0, seed=0)["B_env"]
    return {key: evaluated[key] for key in METRICS}


def _index_digest(indices):
    return hashlib.sha256(np.asarray(indices, dtype=np.int64).tobytes()).hexdigest()


def run_experiment(Xtr, ytr, Xte, yte, test_counts, *,
                   expected_baseline=BASELINE_CAPTURE, fit=fit_model, settings=SETTINGS):
    """Score the unweighted baseline first, then refit only the fixed mining settings."""
    baseline_model = fit(Xtr, ytr)
    baseline_scores = baseline_model.predict_proba(Xte)[:, 1]
    baseline_metrics = _metrics(baseline_scores, yte, test_counts)
    baseline = baseline_metrics["capture@5%"]
    if abs(baseline - expected_baseline) > 1e-9:
        raise ValueError(f"baseline capture@5% did not reproduce: {baseline:.12f}"
                         f" vs {expected_baseline:.12f}; candidates were not run")
    print(f"baseline capture@5%={baseline:.12f} reproduced", flush=True)
    rows = [{"setting": "baseline", "n_train": int(len(ytr)),
             "n_positive": int(ytr.sum()), "n_negative": int((~ytr).sum()),
             "delta_capture@5%": 0.0, **baseline_metrics}]

    # In-sample scores on the 2023 training negatives only. No 2024 labels
    # influence their selection; 2024 is used only for the fixed evaluation.
    train_scores = baseline_model.predict_proba(Xtr)[:, 1]
    for label, n_hard in settings:
        selected, hard, random = select_indices(ytr, train_scores, n_hard, seed=0)
        model = fit(Xtr[selected], ytr[selected])
        scores = model.predict_proba(Xte)[:, 1]
        evaluated = _metrics(scores, yte, test_counts)
        row = {"setting": label, "hard_negative": n_hard, "random_negative": n_hard,
               "n_train": int(len(selected)), "n_positive": int(ytr.sum()),
               "n_negative": 2 * n_hard, "selected_indices_sha256": _index_digest(selected),
               "hard_indices_sha256": _index_digest(hard),
               "random_indices_sha256": _index_digest(random),
               "delta_capture@5%": evaluated["capture@5%"] - baseline, **evaluated}
        rows.append(row)
        print(f"{label} capture@5%={row['capture@5%']:.12f}"
              f" delta={row['delta_capture@5%']:+.12f}", flush=True)
    return rows


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    import sklearn

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path, help="existing B1 artifact directory")
    ap.add_argument("out", type=Path, help="small JSON result path")
    args = ap.parse_args()
    source_hashes = {name: sha256(args.art / name) for name in INPUTS}
    static, counts, muni = load_b1(args.art)
    Xtr, names, ytr, _ = me.design(static, counts, muni, 2023, history=False)
    Xte, test_names, yte, test_counts = me.design(static, counts, muni, 2024, history=False)
    if names != test_names or len(ytr) != 1_168_211 or int(ytr.sum()) != 3_439 \
            or len(yte) != 1_168_211 or int(yte.sum()) != 1_492:
        raise ValueError("B1 columns, cell count, or positive counts differ from the existing experiment")
    rows = run_experiment(Xtr, ytr, Xte, yte, test_counts)
    best = max(rows[1:], key=lambda row: row["delta_capture@5%"])
    result = {
        "mode": "exploratory",
        "question": "Does hard-negative mining alone improve B_env capture@5% on B1?",
        "setup": {"train_year": 2023, "test_year": 2024, "model": "B_env",
                  "settings": [{"name": name, "hard_negative": n, "random_negative": n}
                               for name, n in SETTINGS],
                  "hard_negative_source": "baseline in-sample scores on 2023 negative cells",
                  "random_pool": "2023 negative cells not selected as hard negatives",
                  "random_seed": 0, "sample_weight_passed": False,
                  "hgb": me.HGB, "feature_names": names,
                  "n_train": int(len(ytr)), "n_train_positive": int(ytr.sum()),
                  "n_test": int(len(yte)), "n_test_positive": int(yte.sum()),
                  "numpy": np.__version__, "sklearn": sklearn.__version__,
                  "input_sha256": source_hashes,
                  "baseline_reference_capture@5%": BASELINE_CAPTURE,
                  "baseline_check_tolerance": 1e-9},
        "results": rows,
        "decision": {"improved_settings": [r["setting"] for r in rows[1:]
                                            if r["delta_capture@5%"] > 0],
                     "best_setting": best["setting"] if best["delta_capture@5%"] > 0 else None,
                     "best_delta_capture@5%": max(0.0, best["delta_capture@5%"]),
                     "mining_alone_improved_b1": best["delta_capture@5%"] > 0},
        "limitations": "B1 exploration only; in-sample mining may favor model mistakes."
                       " No 2025/2026 evaluation, uncertainty interval, or deployment claim.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
