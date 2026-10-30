"""B3: cell x year models with and without the year's rain, and the rain shuffled across years.

uv run --with 'duckdb>=1.5.5' --with numpy --with scikit-learn --with scipy python scripts/04_rain_panel.py \
    --grid grid_100 --out outputs/b3_main.json

Rows: cells x years 1976-2019 (1974-1975 have no AMeDAS in the mainland). A row is positive when a record
polygon of that year touches the cell. Rain: the cell's nearest mainland station with values that year:
the year's greatest hourly amount, greatest daily amount, and hours of 30 mm or more.
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
from pyproj import Transformer
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, log_loss

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a/raw"
STATIC = ["elev", "rel_elev_300", "rel_elev_1000", "elev_min_rel", "slope_sd", "d_waterway", "d_river_open",
          "built", "water", "tree", "rain_clim"]
RAIN = ["r_max1h", "r_maxday", "r_h30"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="grid_100")
    ap.add_argument("--years", type=int, nargs=2, default=[1976, 2019])
    ap.add_argument("--test-from", type=int, default=1997)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--block", type=float, default=2000)
    ap.add_argument("--B", type=int, default=1000)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    gdir = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a" / a.grid
    c = duckdb.connect()
    cells = c.execute(f"select * from '{gdir}/cells.parquet'").fetchnumpy()
    n = len(cells["ix"])
    years = np.arange(a.years[0], a.years[1] + 1)

    # rain per station and year
    st = c.execute(f"select station_id, lon, lat from '{RAW}/rain_stations.parquet' where lat > 35.4 and lon < 140.2").fetchall()
    t = Transformer.from_crs("EPSG:6668", "EPSG:6677", always_xy=True)
    sx, sy = t.transform([s[1] for s in st], [s[2] for s in st])
    ids = [s[0] for s in st]
    ry = c.execute(f"""select station_id, year(time_end - interval 1 hour) y, max(precip_mm), count(*) filter (where precip_mm >= 30),
        count(precip_mm) from '{RAW}/rain_hourly.parquet' group by all""").fetchall()
    rd = dict(((r[0], r[1]), r[2]) for r in c.execute(f"select station_id, year(date), max(precip_mm) from '{RAW}/rain_daily.parquet' group by all").fetchall())
    rain = {(r[0], r[1]): (r[2], rd.get((r[0], r[1])), r[3]) for r in ry if r[4] >= 0.8 * 8760}
    d2 = (cells["x"][:, None] - np.array(sx)[None]) ** 2 + (cells["y"][:, None] - np.array(sy)[None]) ** 2
    order_st = np.argsort(d2, axis=1)

    def rain_for(yr, table):
        out = np.full((n, 3), np.nan); used = np.full(n, -1)
        for j in range(len(ids)):
            todo = used < 0
            if not todo.any():
                break
            for s in np.unique(order_st[todo, j]):
                v = table.get((ids[s], yr))
                if v is None:
                    continue
                m = todo & (order_st[:, j] == s)
                out[m] = v; used[m] = s
        return out, used

    # shuffled: each station's years permuted (same permutation for the three rain values)
    rng = np.random.default_rng(0)
    shuf = {}
    for s in ids:
        ys = sorted(y for (st_, y) in rain if st_ == s)
        perm = rng.permutation(ys)
        for y0, y1 in zip(ys, perm):
            shuf[(s, y0)] = rain[(s, y1)]

    fy = c.execute(f"select cell, year from '{gdir}/flood_cell_year.parquet'").fetchnumpy()
    pos = set(zip(fy["cell"].tolist(), fy["year"].tolist()))
    S = np.column_stack([cells[f].astype(float) for f in STATIC])
    Xs, Xr, Xsh, Y, YR, CELL = [], [], [], [], [], []
    stations_used = {}
    for yr in years:
        r, used = rain_for(int(yr), rain)
        r2, _ = rain_for(int(yr), shuf)
        stations_used[int(yr)] = int(len(np.unique(used)))
        Xs.append(S); Xr.append(r); Xsh.append(r2)
        Y.append(np.array([(i, int(yr)) in pos for i in range(n)]))
        YR.append(np.full(n, yr)); CELL.append(np.arange(n))
    Xs, Xr, Xsh = np.vstack(Xs), np.vstack(Xr), np.vstack(Xsh)
    Y, YR, CELL = np.concatenate(Y), np.concatenate(YR), np.concatenate(CELL)
    tr, te = YR < a.test_from, YR >= a.test_from

    def fit(X):
        p = np.zeros(te.sum())
        for s in range(a.seeds):
            m = HistGradientBoostingClassifier(max_iter=300, random_state=s).fit(X[tr], Y[tr])
            p += m.predict_proba(X[te])[:, 1] / a.seeds
        return p

    preds = {"static": fit(Xs), "static_rain": fit(np.column_stack([Xs, Xr])), "static_rain_shuffled": fit(np.column_stack([Xs, Xsh]))}
    yte = Y[te]
    blocks_cell = np.floor(cells["x"] / a.block).astype(np.int64) * 100000 + np.floor(cells["y"] / a.block).astype(np.int64)
    bid, binv = np.unique(blocks_cell[CELL[te]], return_inverse=True)
    res = {"args": vars(a), "rows_train": int(tr.sum()), "rows_test": int(te.sum()), "pos_train": int(Y[tr].sum()),
           "pos_test": int(yte.sum()), "blocks": int(len(bid)), "stations_used_per_year": stations_used, "models": {}}
    for k, p in preds.items():
        yr_true = np.bincount(YR[te] - a.test_from, weights=yte.astype(float))
        yr_pred = np.bincount(YR[te] - a.test_from, weights=p)
        res["models"][k] = {"ap": float(average_precision_score(yte, p)), "log_loss": float(log_loss(yte, np.clip(p, 1e-9, 1 - 1e-9))),
                            "mean_pred": float(p.mean()), "year_spearman": float(spearmanr(yr_true, yr_pred).statistic)}
    res["base_rate_test"] = float(yte.mean())
    res["diffs"] = []
    for x, y in [("static_rain", "static"), ("static_rain_shuffled", "static"), ("static_rain", "static_rain_shuffled")]:
        d = np.empty(a.B)
        for b in range(a.B):
            w = np.bincount(rng.integers(0, len(bid), len(bid)), minlength=len(bid)).astype(float)[binv]
            d[b] = average_precision_score(yte, preds[x], sample_weight=w) - average_precision_score(yte, preds[y], sample_weight=w)
        res["diffs"].append({"a": x, "b": y, "diff": res["models"][x]["ap"] - res["models"][y]["ap"],
                             "lo90": float(np.quantile(d, 0.05)), "hi90": float(np.quantile(d, 0.95))})
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k not in ("stations_used_per_year", "args")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
