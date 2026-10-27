"""Diagnostic same-year spatial OOF for the fixed B_env HGB; not a forecast.

From the repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --with numpy --with scipy --with scikit-learn --with pandas --with pyarrow \
      python projects/akita-bear-risk-grid-100m/scripts/same_year_spatial_oof.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/akita-bear-risk-grid-100m \
      projects/akita-bear-risk-grid-100m/outputs/b2_b3_same_year_spatial_oof.json
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

import features as ft
import metrics as mt
import model_eval as me

SPLITS = {"B2": (2025, "b2_confirm_2023-2024_to_2025"),
          "B3": (2026, "b3_confirm_2023-2025_to_2026")}
METRICS = ("capture@1%", "capture@5%", "capture@10%", "auc", "ap")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_folds(ix, iy):
    """Assign the existing 10km squares to one label-free GroupKFold split."""
    from sklearn.model_selection import GroupKFold

    ix, iy = np.asarray(ix), np.asarray(iy)
    if ix.ndim != 1 or iy.shape != ix.shape or len(ix) == 0:
        raise ValueError("grid indices must be aligned non-empty vectors")
    blocks = (ix // 100) * 10000 + iy // 100
    if len(np.unique(blocks)) < 5:
        raise ValueError("fewer than five spatial blocks")
    fold = np.full(len(ix), -1, dtype=np.int8)
    for f, (_, test) in enumerate(GroupKFold(n_splits=5).split(ix, groups=blocks)):
        if np.any(fold[test] != -1):
            raise ValueError("cell assigned to multiple folds")
        fold[test] = f
    if np.any(fold < 0):
        raise ValueError("some cells have no fold")
    return blocks, fold


def oof_scores(X, y, blocks, fold, model_factory=None):
    """Fit five unchanged HGBs, predicting only blocks held out from each fit."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    X, y, blocks, fold = map(np.asarray, (X, y, blocks, fold))
    n = len(y)
    if X.ndim != 2 or X.shape[0] != n or y.shape != (n,) or y.dtype != bool \
            or blocks.shape != (n,) or fold.shape != (n,) or set(fold.tolist()) != set(range(5)):
        raise ValueError("features, binary labels, blocks or five folds invalid")
    for block in np.unique(blocks):
        if len(np.unique(fold[blocks == block])) != 1:
            raise ValueError("block crosses folds")
    if model_factory is None:
        model_factory = lambda: HistGradientBoostingClassifier(**me.HGB, random_state=0)
    scores = np.full(n, np.nan, dtype=np.float64)
    diagnostics = []
    for f in range(5):
        test = fold == f
        train = ~test
        if not test.any() or np.unique(y[train]).size != 2 or np.unique(y[test]).size != 2:
            raise ValueError(f"fold {f} has empty partition or lacks a class")
        if np.intersect1d(blocks[train], blocks[test]).size:
            raise ValueError("training contains held-out block")
        model = model_factory()
        model.fit(X[train], y[train])
        pred = np.asarray(model.predict_proba(X[test])[:, 1], dtype=np.float64)
        if pred.shape != (int(test.sum()),) or not np.isfinite(pred).all():
            raise ValueError("invalid OOF scores")
        scores[test] = pred
        diagnostics.append({"fold": f, "n_train": int(train.sum()),
                            "n_test": int(test.sum()), "positive_train": int(y[train].sum()),
                            "positive_test": int(y[test].sum()),
                            "n_test_blocks": int(np.unique(blocks[test]).size)})
    if not np.isfinite(scores).all():
        raise ValueError("some cells were not predicted")
    return scores, diagnostics


def score_metrics(scores, positive):
    from sklearn.metrics import average_precision_score, roc_auc_score

    order = mt.rank_order(scores, seed=0)
    out = {f"capture@{int(k * 100)}%": mt.capture(order, positive, k)
           for k in (0.01, 0.05, 0.10)}
    out["auc"] = float(roc_auc_score(positive, scores))
    out["ap"] = float(average_precision_score(positive, scores))
    return out


def main():
    import pandas as pd
    import sklearn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("art", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    prior = json.loads((project / "outputs/b1_poisson_target_isolation.json").read_text(encoding="utf-8"))
    source_names = ("worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz",
                    "reports_by_year.npz", "grid_mask.npz")
    hashes = {name: sha256(args.art / name) for name in source_names}
    if hashes != prior["setup"]["input_sha256"]:
        raise ValueError("input versions differ from fixed B_env experiment")
    cells_path = args.art / "cells.parquet"
    hashes["cells.parquet"] = sha256(cells_path)
    with np.load(args.art / "grid_mask.npz") as grid:
        inside = grid["muni"] >= 0
    iy, ix = np.nonzero(inside)
    cells = pd.read_parquet(cells_path, columns=["ix", "iy"])
    if not np.array_equal(cells["ix"].to_numpy(), ix) or not np.array_equal(cells["iy"].to_numpy(), iy):
        raise ValueError("cells.parquet order differs from feature/label arrays")
    blocks, fold = fixed_folds(ix, iy)
    fold_path = args.out.with_name(args.out.stem + "_folds.csv")
    fold_path.parent.mkdir(parents=True, exist_ok=True)
    with fold_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("block", "fold", "n_cells"))
        for block in np.unique(blocks):
            rows = blocks == block
            writer.writerow((int(block), int(fold[rows][0]), int(rows.sum())))
    hashes["folds.csv"] = sha256(fold_path)

    with np.load(args.art / "worldcover.npz") as wc, np.load(args.art / "dem.npz") as dem, \
            np.load(args.art / "worldpop.npz") as pop, np.load(args.art / "osm.npz") as osm:
        static = ft.static_features(wc, dem, pop, osm)
    names = list(static)
    if names != prior["setup"]["feature_names"] or len(names) != 28:
        raise ValueError("static B_env features changed")
    X = np.column_stack([static[name][inside] for name in names]).astype(np.float32)
    del static
    years = {}
    with np.load(args.art / "reports_by_year.npz") as labels:
        for block_name, (year, stem) in SPLITS.items():
            ref_path = args.art / "eval" / f"{stem}.json"
            ref = json.loads(ref_path.read_text(encoding="utf-8"))
            hashes[f"eval/{stem}.json"] = sha256(ref_path)
            y = labels[f"c{year}"][inside] > 0
            if ref["setup"]["test"] != year or ref["setup"]["hgb"] != me.HGB \
                    or ref["n_cells"] != len(y) or ref["n_pos_cells"] != int(y.sum()):
                raise ValueError(f"{block_name}: temporal reference or labels differ")
            temporal = {key: ref["B_env"][key] for key in METRICS}
            scores, diag = oof_scores(X, y, blocks, fold)
            oof = score_metrics(scores, y)
            years[block_name] = {"year": year, "n_cells": len(y), "n_positive": int(y.sum()),
                                 "fold_diagnostics": diag, "temporal_B_env": temporal,
                                 "same_year_spatial_oof": oof,
                                 "delta_capture@5%": oof["capture@5%"] - temporal["capture@5%"]}
            print(f"{block_name}: temporal={temporal['capture@5%']:.9f}, "
                  f"OOF={oof['capture@5%']:.9f}, delta={years[block_name]['delta_capture@5%']:+.9f}",
                  flush=True)
    result = {"purpose": "descriptive same-year spatial OOF diagnostic; not a future forecast or model selection",
              "setup": {"feature_names": names, "hgb": me.HGB, "random_state": 0,
                        "block_formula": "(ix//100)*10000+iy//100",
                        "splitter": "GroupKFold(n_splits=5, shuffle=False)",
                        "n_blocks": int(np.unique(blocks).size), "fold_table": str(fold_path),
                        "sklearn_version": sklearn.__version__, "input_sha256": hashes},
              "years": years,
              "limitations": ["same-year labels are used for training in other blocks; this is not an operational forecast",
                              "block-edge spatial dependence remains without a buffer",
                              "OOF versus temporal differs in train years, spatial holdout and training size, so it does not isolate nonstationarity",
                              "2026 labels cover April-September only; report locations and observation effort are imperfect"]}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
