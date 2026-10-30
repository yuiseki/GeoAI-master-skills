"""Gate 5 and the explanation of the static model: residual autocorrelation by distance, and permutation importance.

uv run --with 'duckdb>=1.5.5' --with numpy --with scikit-learn python scripts/09_checks.py --out outputs/checks.json

Residual: test label (1997-2019) minus the static model's score, standardised by its sum so that it is on the
scale of the labels. Moran's I at lag d uses the cells exactly d cells away along a row or a column (rook steps
of d), and is reported next to the same statistic for the labels themselves. A residual that is still
correlated at 2 km would mean the 2 km blocks of the intervals are too small (the 5 km run is the check).

Permutation importance: the drop in capture@k_A of the test labels when one feature is shuffled across cells
(5 shuffles each). It says which inputs the model's ranking leans on, not what causes flooding.
"""
import argparse
import json
from pathlib import Path

import numpy as np

import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("static", HERE / "03_static.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
sr, ROOT = st.sr, st.ROOT


def morans_i_lag(v, ix, iy, d):
    """Moran's I of v over pairs of cells d steps apart in x or in y (both directions counted once)."""
    nx, ny = ix.max() + 1, iy.max() + 1
    a = np.full((ny, nx), np.nan)
    a[iy, ix] = v - v.mean()
    num = 0.0; w = 0
    for p, q in [(a[:, d:], a[:, :-d]), (a[d:, :], a[:-d, :])]:
        m = ~np.isnan(p) & ~np.isnan(q)
        num += float((p[m] * q[m]).sum()); w += int(m.sum())
    return len(v) / w * num / float(((v - v.mean()) ** 2).sum()), w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="grid_100")
    ap.add_argument("--train", type=int, nargs=2, default=[1974, 1996])
    ap.add_argument("--test", type=int, nargs=2, default=[1997, 2019])
    ap.add_argument("--lags", type=int, nargs="+", default=[1, 2, 5, 10, 20, 50])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    gdir = ROOT / "artifacts/tokyo23-flood-record-vs-a31a" / a.grid
    cells, (ytr, _, _, _), (yte, _, _, _) = st.load(gdir, a.train, a.test, "any", "all")
    n = len(ytr)
    X = np.column_stack([cells[f].astype(float) for f in st.FEATURES])
    k_a = float((cells["a31a_maximum"] > 0).mean())

    from sklearn.ensemble import HistGradientBoostingClassifier
    models = [HistGradientBoostingClassifier(max_iter=300, random_state=s).fit(X, ytr) for s in range(5)]

    def score(Xp):
        return sum(m.predict_proba(Xp)[:, 1] for m in models) / len(models)

    p = score(X)
    base = sr.capture(sr.rank_order(p, None, seed=0), yte, k_a)
    resid = yte.astype(float) - p * yte.sum() / p.sum()
    ix, iy = cells["ix"], cells["iy"]
    size = json.loads((gdir / "audit.json").read_text())["size"]
    res = {"args": vars(a), "k_a31a": k_a, "capture_kA": base, "moran": [], "importance": {}}
    for d in a.lags:
        i_r, w = morans_i_lag(resid, ix, iy, d)
        i_y, _ = morans_i_lag(yte.astype(float), ix, iy, d)
        i_tr, _ = morans_i_lag(ytr.astype(float), ix, iy, d)
        res["moran"].append({"lag_cells": d, "lag_m": d * size, "pairs": w, "I_resid": i_r, "I_test_label": i_y, "I_train_label": i_tr})
    rng = np.random.default_rng(0)
    for j, f in enumerate(st.FEATURES):
        drops = []
        for _ in range(5):
            Xp = X.copy(); Xp[:, j] = X[rng.permutation(n), j]
            drops.append(base - sr.capture(sr.rank_order(score(Xp), None, seed=0), yte, k_a))
        res["importance"][f] = {"mean_drop": float(np.mean(drops)), "min": float(np.min(drops)), "max": float(np.max(drops))}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
