"""F1, role permutation: split the 22 B and H features at random into halves of the same sizes (10 and 12), fit the
B_env model on each half, and compare the real B/H split with 20 random ones (seeds 0-19) on one split.

Statistics (all symmetric in the two halves): |capture@5% difference| on the test year (bear-year labels, as in the
evaluation), the larger of the two captures, the Spearman correlation of the two halves' scores over all cells, and
the JSD between the 25-bin composition of the test year's April-September positive cells and that of all cells.
The real split's values come from its own scores (interface_models.py) and are recomputed here the same way.

From repository root (one split per call; B2 and B3 can run side by side):
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      uvx --with numpy==2.5.4 --with scipy --with scikit-learn==1.9.1 --with pandas --with pyarrow python \
      projects/_bear/akita-bear-human-interface/scripts/interface_role_perm.py artifacts/_bear/akita-bear-risk-grid-100m \
      artifacts/_bear/akita-bear-human-interface --train 2023 2024 --test 2025 \
      --out projects/_bear/akita-bear-human-interface/outputs/f1_role_perm_b2.json
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

import interface_models as im
import metrics as mt
import phase as ph

N_PERM = 20
REAL = {(2023, 2024, 2025): "b2_confirm_2023-2024_to_2025.npz", (2023, 2024, 2025, 2026): "b3_confirm_2023-2025_to_2026.npz",
        (2023, 2024): "b1_dev_2023_to_2024.npz"}


def random_split(features, n_first, seed):
    rng = np.random.default_rng(seed)
    pick = set(rng.permutation(len(features))[:n_first].tolist())
    return [f for i, f in enumerate(features) if i in pick], [f for i, f in enumerate(features) if i not in pick]


def stats(s1, s2, y_test, season_pos):
    from scipy.stats import spearmanr

    c1 = mt.capture(mt.rank_order(s1), y_test, 0.05)
    c2 = mt.capture(mt.rank_order(s2), y_test, 0.05)
    p1, p2 = ph.percentile(s1), ph.percentile(s2)
    q1, q2 = ph.quintile(p1), ph.quintile(p2)
    return {"cap_1": c1, "cap_2": c2, "abs_cap_diff": abs(c1 - c2), "max_cap": max(c1, c2),
            "spearman": float(spearmanr(p1, p2).statistic),
            "jsd_pos_vs_cells": ph.jsd(ph.bin_counts(q1, q2, season_pos), ph.bin_counts(q1, q2, np.ones_like(season_pos)))}


LOW_IS_DISTINCT = ("spearman",)  # less correlated axes separate the cells more


def rank_of_real(real, perms, key):
    """Rank of the real value among the 21 (1 = the most distinct: the largest, or the smallest for spearman)."""
    if key in LOW_IS_DISTINCT:
        return 1 + sum(p[key] <= real[key] for p in perms)
    return 1 + sum(p[key] >= real[key] for p in perms)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("--train", type=int, nargs="+", required=True)
    a.add_argument("--test", type=int, required=True)
    a.add_argument("--out", type=Path, required=True)
    args = a.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists")
    t0 = time.time()
    hashes = im.check_inputs(args.art)
    X, names, counts, muni = im.static_matrix(args.art)
    roles = im.load_roles(im.ROLES_FILE, names)
    pool = [f for f in names if f in roles["B"] or f in roles["H"]]
    inside = muni >= 0
    y_test, _ = im.labels(counts, muni, args.test)
    season = np.load(args.work / "labels/season_counts.npz")[f"s{args.test}"][inside] > 0
    real_file = args.work / "scores" / REAL[tuple(args.train + [args.test])]
    z = np.load(real_file)
    real = stats(z["M_B"].astype(float), z["M_H"].astype(float), y_test, season)
    print("real", {k: round(v, 4) for k, v in real.items()}, flush=True)
    perms = []
    for seed in range(N_PERM):
        h1, h2 = random_split(pool, len(roles["B"]), seed)
        s = im.fit_scores(X, names, counts, muni, args.train, {"half_1": h1, "half_2": h2})
        st = stats(s["half_1"], s["half_2"], y_test, season)
        st.update({"seed": seed, "half_1": h1, "half_2": h2,
                   "half_1_bear_side": sum(f in roles["B"] for f in h1)})
        perms.append(st)
        print(seed, {k: round(v, 4) for k, v in st.items() if isinstance(v, float)}, flush=True)
    keys = ("abs_cap_diff", "max_cap", "spearman", "jsd_pos_vs_cells")
    out = {"derived": "model scores on random feature halves (falsification); not observations",
           "train": args.train, "test": args.test, "n_perm": N_PERM, "real": real, "real_scores": real_file.name,
           "real_scores_sha256": im.sha256(real_file), "perms": perms,
           "rank_of_real_among_21": {k: rank_of_real(real, perms, k) for k in keys},
           "perm_quantiles": {k: {q: float(np.quantile([p[k] for p in perms], q)) for q in (0.05, 0.5, 0.95)} for k in keys},
           "rule": "real is distinguished from arbitrary splits on a statistic if its rank is 1 or 2 of 21 (rank 1 = largest, or smallest for spearman)",
           "input_sha256": hashes, "seconds": round(time.time() - t0)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(out["rank_of_real_among_21"])


if __name__ == "__main__":
    main()
