"""B1, B2, B4: static maps against A31a, scored on the records of a later period by capture@k.

uv run --with 'duckdb>=1.5.5' --with numpy --with scikit-learn --with pyarrow python scripts/03_static.py \
    --grid grid_100 --train 1974 1996 --test 1997 2019 [--label any|centre] [--a31a maximum|planned|maximum_0.5]
    [--block 2000] [--reason all|naisui|issui] --out outputs/b1_main.json

Every map is ranked with the same rule (score, then a secondary key, then a seeded random number) and
scored on the same cells and positives. Intervals: blocks of --block metres drawn with replacement 1,000
times, the top k chosen again in every draw.
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".agents/skills/grid-risk-mapping/scripts"))
import grid_cells as gc  # noqa: E402
import score_risk_map as sr  # noqa: E402

FEATURES = ["elev", "rel_elev_300", "rel_elev_1000", "elev_min_rel", "slope_sd", "d_waterway", "d_river_open",
            "built", "water", "tree", "rain_clim"]
KS = [0.01, 0.05, 0.10, 0.20]


def load(grid_dir, train, test, label, reason):
    c = duckdb.connect()
    cells = c.execute(f"select * from '{grid_dir}/cells.parquet'").fetchnumpy()
    n = len(cells["ix"])
    cond = {"any": "true", "centre": "centre_in"}[label]
    cond += {"all": "", "naisui": " and naisui", "issui": " and issui"}[reason]
    fy = c.execute(f"select cell, year, n_poly from '{grid_dir}/flood_cell_year.parquet' where {cond}").fetchnumpy()

    def period(y0, y1):
        m = (fy["year"] >= y0) & (fy["year"] <= y1)
        pos = np.zeros(n, bool); pos[fy["cell"][m]] = True
        cnt = np.bincount(fy["cell"][m], weights=fy["n_poly"][m], minlength=n)
        return pos, cnt, fy["cell"][m], fy["year"][m]

    return cells, period(*train), period(*test)


def history(cells, cell_ids, years, size):
    """Records of the training period: each year's flooded cells weighted by 1 / (cells flooded that year), summed
    over the cell and the squares around it (300 m and 1 km)."""
    ix, iy = cells["ix"], cells["iy"]
    nx, ny = ix.max() + 1, iy.max() + 1
    a = np.zeros((ny, nx))
    for y in np.unique(years):
        m = years == y
        np.add.at(a, (iy[cell_ids[m]], ix[cell_ids[m]]), 1.0 / m.sum())
    out = {"h_cell": a[iy, ix]}
    for name, r in [("h_300", max(1, int(round(150 / size)))), ("h_1000", max(1, int(round(500 / size))))]:
        out[name] = gc.box_sum(a, r)[iy, ix]
    return out


def fit_predict(X, y, seeds=5):
    p = np.zeros(len(y))
    for s in range(seeds):
        m = HistGradientBoostingClassifier(max_iter=300, random_state=s)
        m.fit(X, y)
        p += m.predict_proba(X)[:, 1] / seeds
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="grid_100")
    ap.add_argument("--train", type=int, nargs=2, default=[1974, 1996])
    ap.add_argument("--test", type=int, nargs=2, default=[1997, 2019])
    ap.add_argument("--label", default="any", choices=["any", "centre"])
    ap.add_argument("--a31a", default="maximum", choices=["maximum", "planned", "maximum_0.5"])
    ap.add_argument("--block", type=float, default=2000)
    ap.add_argument("--reason", default="all", choices=["all", "naisui", "issui"])
    ap.add_argument("--B", type=int, default=1000)
    ap.add_argument("--maps-out")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    grid_dir = ROOT / "artifacts/tokyo23-flood-record-vs-a31a" / a.grid
    size = json.loads((grid_dir / "audit.json").read_text())["size"]
    cells, (ytr, _, tr_cells, tr_years), (yte, cte, _, _) = load(grid_dir, a.train, a.test, a.label, a.reason)
    n = len(ytr)
    X = np.column_stack([cells[f].astype(float) for f in FEATURES])
    H = history(cells, tr_cells, tr_years, size)
    rng = np.random.default_rng(0)

    a31a_col, a31a_min = {"maximum": ("a31a_maximum", 1), "planned": ("a31a_planned", 1), "maximum_0.5": ("a31a_maximum", 2)}[a.a31a]
    a31a_score = np.where(cells[a31a_col] >= a31a_min, cells[a31a_col], 0).astype(float)
    k_a = float((a31a_score > 0).mean())

    p_static = fit_predict(X, ytr)
    Xh = np.column_stack([X] + [H[k] for k in ["h_cell", "h_300", "h_1000"]])
    p_hist = fit_predict(Xh, ytr)
    Hp = np.column_stack([H[k][rng.permutation(n)] for k in ["h_cell", "h_300", "h_1000"]])
    p_hist_perm = fit_predict(np.column_stack([X, Hp]), ytr)

    maps = {
        "random": (np.zeros(n), None),
        "elev_low": (-np.nan_to_num(cells["elev"].astype(float), nan=np.inf), None),
        "a31a": (a31a_score, cells["a31a_planned"].astype(float)),
        "history_density": (H["h_300"], H["h_cell"]),
        "model_static": (p_static, None),
        "model_static_history": (p_hist, None),
        "model_history_permuted": (p_hist_perm, None),
    }
    orders = {k: sr.rank_order(s, second, seed=0) for k, (s, second) in maps.items()}
    blocks = (np.floor(cells["x"] / a.block).astype(np.int64) * 100000 + np.floor(cells["y"] / a.block).astype(np.int64))
    res = {"args": vars(a), "cells": n, "train_pos": int(ytr.sum()), "test_pos": int(yte.sum()),
           "test_records_in_cells": float(cte.sum()), "k_a31a": k_a, "blocks": int(len(np.unique(blocks))),
           "features": FEATURES, "maps": {}}
    for k_, o in orders.items():
        s = maps[k_][0]
        res["maps"][k_] = {
            "capture_kA": sr.capture(o, yte, k_a),
            **{f"capture_{int(k*100)}": sr.capture(o, yte, k) for k in KS},
            "capture_count_kA": sr.capture(o, cte, k_a),
            "auc": float(roc_auc_score(yte, np.nan_to_num(s, nan=-1e9))) if k_ != "random" else 0.5,
        }
    pairs = [("model_static", "a31a", k_a), ("a31a", "random", k_a), ("model_static_history", "model_static", k_a),
             ("model_history_permuted", "model_static", k_a), ("model_static", "a31a", 0.05), ("model_static", "a31a", 0.10),
             ("model_static", "elev_low", k_a), ("model_static", "history_density", k_a)]
    res["diffs"] = []
    for x, y, k in pairs:
        lo, hi = sr.bootstrap_diff(orders[x], orders[y], yte, blocks, k, B=a.B, seed=0)
        res["diffs"].append({"a": x, "b": y, "k": k, "diff": sr.capture(orders[x], yte, k) - sr.capture(orders[y], yte, k), "lo90": lo, "hi90": hi})
    # overlap of the model's top k_A with the A31a area, and where the test positives fall
    top = np.zeros(n, bool); top[orders["model_static"][: int(round(k_a * n))]] = True
    inA = a31a_score > 0
    res["overlap"] = {"model_top_in_a31a": float((top & inA).sum() / top.sum()),
                      "test_pos_in_a31a_only": int((yte & inA & ~top).sum()), "test_pos_in_model_only": int((yte & top & ~inA).sum()),
                      "test_pos_in_both": int((yte & top & inA).sum()), "test_pos_in_neither": int((yte & ~top & ~inA).sum())}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if a.maps_out:
        import pyarrow as pa, pyarrow.parquet as pq
        cols = {"cell": np.arange(n), "ix": cells["ix"], "iy": cells["iy"], "x": cells["x"], "y": cells["y"], "test_pos": yte,
                "a31a": a31a_score, "model_static": p_static, "model_static_history": p_hist, "elev": cells["elev"]}
        for k_, o in orders.items():
            r = np.empty(n, dtype=np.int64); r[o] = np.arange(n); cols[f"rank_{k_}"] = r
        pq.write_table(pa.table(cols), a.maps_out)
    print(json.dumps({k: res[k] for k in ["cells", "train_pos", "test_pos", "k_a31a", "blocks"]}))
    for k_, v in res["maps"].items():
        print(f"{k_:24s} " + " ".join(f"{m}={v[m]:.3f}" for m in v))
    for d in res["diffs"]:
        print(f"{d['a']} - {d['b']} @ {d['k']:.3f}: {d['diff']:+.3f} [{d['lo90']:+.3f}, {d['hi90']:+.3f}]")
    print(res["overlap"])


if __name__ == "__main__":
    main()
