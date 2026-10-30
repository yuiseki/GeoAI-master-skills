"""B4b (exploratory): the history features built before the label period, as grid-risk-mapping asks.

B4 in 03_static.py trained on the labels of 1974-1996 with history features made from the same records, so
the model learned "label = history" (a leak inside the training rows). Here the training rows use history
of 1974-1985 and labels of 1986-1996; the test rows use history of 1974-1996 and labels of 1997-2019.
The comparator is the static model trained on the same labels (1986-1996).

uv run --with 'duckdb>=1.5.5' --with numpy --with scikit-learn python scripts/05_history.py --out outputs/b4b.json
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("static", HERE / "03_static.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
sr, ROOT = st.sr, st.ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="grid_100")
    ap.add_argument("--hist-train", type=int, nargs=2, default=[1974, 1985])
    ap.add_argument("--label-train", type=int, nargs=2, default=[1986, 1996])
    ap.add_argument("--test", type=int, nargs=2, default=[1997, 2019])
    ap.add_argument("--B", type=int, default=1000)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    gdir = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a" / a.grid
    size = json.loads((gdir / "audit.json").read_text())["size"]
    cells, (h0, _, h0c, h0y), (yte, _, _, _) = st.load(gdir, a.hist_train, a.test, "any", "all")
    _, (ytr, _, _, _), (_, _, hallc, hally) = st.load(gdir, a.label_train, (a.hist_train[0], a.label_train[1]), "any", "all")
    n = len(ytr)
    X = np.column_stack([cells[f].astype(float) for f in st.FEATURES])
    keys = ["h_cell", "h_300", "h_1000"]
    Htr = st.history(cells, h0c, h0y, size)
    Hte = st.history(cells, hallc, hally, size)
    rng = np.random.default_rng(0)

    def fit(Xtr, Xte):
        from sklearn.ensemble import HistGradientBoostingClassifier
        p = np.zeros(n)
        for s in range(5):
            p += HistGradientBoostingClassifier(max_iter=300, random_state=s).fit(Xtr, ytr).predict_proba(Xte)[:, 1] / 5
        return p

    p_static = fit(X, X)
    p_hist = fit(np.column_stack([X] + [Htr[k] for k in keys]), np.column_stack([X] + [Hte[k] for k in keys]))
    perm = rng.permutation(n)
    p_perm = fit(np.column_stack([X] + [Htr[k][perm] for k in keys]), np.column_stack([X] + [Hte[k][perm] for k in keys]))
    k_a = float((cells["a31a_maximum"] > 0).mean())
    orders = {k: sr.rank_order(v, None, seed=0) for k, v in {"static_8696": p_static, "static_history": p_hist, "history_permuted": p_perm}.items()}
    blocks = np.floor(cells["x"] / 2000).astype(np.int64) * 100000 + np.floor(cells["y"] / 2000).astype(np.int64)
    res = {"args": vars(a), "train_pos": int(ytr.sum()), "test_pos": int(yte.sum()), "k_a31a": k_a,
           "maps": {k: {"capture_kA": sr.capture(o, yte, k_a), "capture_5": sr.capture(o, yte, 0.05), "capture_10": sr.capture(o, yte, 0.10)} for k, o in orders.items()},
           "diffs": []}
    for x, y in [("static_history", "static_8696"), ("history_permuted", "static_8696")]:
        for k in [k_a, 0.05]:
            lo, hi = sr.bootstrap_diff(orders[x], orders[y], yte, blocks, k, B=a.B, seed=0)
            res["diffs"].append({"a": x, "b": y, "k": k, "diff": sr.capture(orders[x], yte, k) - sr.capture(orders[y], yte, k), "lo90": lo, "hi90": hi})
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
