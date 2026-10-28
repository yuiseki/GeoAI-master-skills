"""Moran's I for allocation differences, plus municipality summaries.

Run from repository root with the analysis venv:
  /tmp/venv-geoai/bin/python projects/_transit/elderly-transit-100m-allocation/scripts/spatial_checks.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix

ROOT = Path(__file__).resolve().parents[4]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.parent.name / PROJECT.name
OUTPUT = PROJECT / "outputs"


def indices(code):
    return (
        int(code[:2]) * 80 + int(code[4]) * 10 + int(code[6]),
        int(code[2:4]) * 80 + int(code[5]) * 10 + int(code[7]),
    )


def queen_weights(codes):
    lookup = {indices(code): code for code in codes}
    rows, cols = [], []
    for code in codes:
        i, j = indices(code)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                neighbor = lookup.get((i + di, j + dj))
                if neighbor is not None:
                    rows.append(code)
                    cols.append(neighbor)
    index = {code: k for k, code in enumerate(codes)}
    rows_i = np.array([index[c] for c in rows], dtype=np.int32)
    cols_i = np.array([index[c] for c in cols], dtype=np.int32)
    data = np.ones(len(rows_i))
    w = coo_matrix((data, (rows_i, cols_i)), shape=(len(codes), len(codes))).tocsr()
    sums = np.asarray(w.sum(axis=1)).ravel()
    sums[sums == 0] = 1.0
    return w.multiply(1.0 / sums[:, None]).tocsr()


def moran(values, codes, permutations=999, seed=20261026):
    values = np.asarray(values, dtype=float)
    mask = np.isfinite(values)
    values = values[mask]
    codes = [code for code, keep in zip(codes, mask) if keep]
    n = len(values)
    if n < 10:
        return {"n": n, "I": None, "p_positive": None, "p_two_sided": None}
    w = queen_weights(codes)
    z = values - values.mean()
    denom = float(z @ z)
    if denom == 0:
        return {"n": n, "I": None, "p_positive": None, "p_two_sided": None}
    observed = float((z @ (w @ z)) / denom)
    rng = np.random.default_rng(seed)
    permuted = np.empty(permutations)
    for k in range(permutations):
        zp = rng.permutation(z)
        permuted[k] = float((zp @ (w @ zp)) / denom)
    p_positive = (1 + int((permuted >= observed).sum())) / (permutations + 1)
    p_two = (1 + int((np.abs(permuted) >= abs(observed)).sum())) / (permutations + 1)
    return {
        "n": n,
        "I": observed,
        "p_positive": p_positive,
        "p_two_sided": p_two,
        "permutations": permutations,
        "mean": float(values.mean()),
        "sd": float(values.std(ddof=1)),
        "neighbors_mean": float(np.asarray(w.sum(axis=1)).mean()),
    }


def main():
    frame = pd.read_parquet(ARTIFACTS / "mesh-allocations.parquet")
    codes = frame["mesh"].tolist()
    frame["difference_age65"] = frame["wpop_age65_main_500"] - frame["center_age65_main_500"]
    frame["difference_fraction"] = frame["wpop_fraction_main_500"] - frame["center_gap_main_500"]
    variables = {
        "center_age65": "center_age65_main_500",
        "wpop_age65": "wpop_age65_main_500",
        "difference_age65": "difference_age65",
        "center_gap": "center_gap_main_500",
        "wpop_fraction": "wpop_fraction_main_500",
        "difference_fraction": "difference_fraction",
        "age65": "age65",
    }
    result = {name: moran(frame[col], codes) for name, col in variables.items()}
    (OUTPUT / "spatial-autocorrelation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )

    frame["center_age65"] = frame["center_age65_main_500"].fillna(0)
    frame["wpop_age65"] = frame["wpop_age65_main_500"].fillna(0)
    by_muni = (
        frame.groupby(["municipality_code", "municipality"])
        .agg(
            meshes=("mesh", "size"),
            age65=("age65", "sum"),
            center_age65=("center_age65", "sum"),
            wpop_age65=("wpop_age65", "sum"),
            difference_age65=("difference_age65", "sum"),
            positive_difference_meshes=("difference_age65", lambda s: int((s > 0).sum())),
            negative_difference_meshes=("difference_age65", lambda s: int((s < 0).sum())),
        )
        .reset_index()
        .sort_values("difference_age65", ascending=False)
    )
    by_muni.to_csv(OUTPUT / "municipality-difference.csv", index=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(by_muni.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
