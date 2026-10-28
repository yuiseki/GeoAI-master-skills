"""Freeze the forecast for the weeks after the end of the data (plan block B5) and write its provenance.

Fits the candidate on every week up to the last origin and forecasts h = 1..8 weeks ahead for each
municipality, directly (one model per h). Alongside it: the baselines naive, mean_short and muni_mean at
the same origin, and the same set from an origin 4 weeks earlier (h = 5..12, the same target weeks, names
ending in `_shift4`), for the robustness comparison of the plan.

Writes OUT_PREFIX.parquet (model, h, origin_week, target_week, code5, pred), and OUT_PREFIX.provenance.json
with the sha256 of the forecast, the inputs, the settings, the versions and what is not checked.

Usage:
    uvx --with numpy --with pandas --with scikit-learn --with pyarrow --with scipy python freeze_forecast.py \
        TABLE.parquet ADJACENCY.parquet OUT_PREFIX [--candidate hgb_nb] [--expect-last 2026-09-21]
"""

import argparse
import datetime as dt
import hashlib
import json
import platform
import sys

import numpy as np
import pandas as pd

import evaluate as ev


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def forecast_rows(Y, dates, pop, codes, W, o, horizons, candidate, suffix=""):
    rows = []
    for h in horizons:
        target = str(dates[o] + np.timedelta64(7 * h, "D"))
        preds = {
            candidate + suffix: ev.model_forecast(candidate, Y, dates, pop, o, h, ev.WEEKLY, W),
            "naive" + suffix: ev.baseline(Y, o, h, "naive", ev.WEEKLY),
            "mean_short" + suffix: ev.baseline(Y, o, h, "mean_short", ev.WEEKLY),
            "muni_mean" + suffix: ev.baseline(Y, o, h, "muni_mean", ev.WEEKLY),
        }
        for name, p in preds.items():
            if not np.isfinite(p).all() or (p < 0).any():
                raise ValueError(f"{name} h={h}: non-finite or negative forecast")
            for i, c in enumerate(codes):
                rows.append((name, h, str(dates[o]), target, c, float(p[i])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table")
    ap.add_argument("adjacency")
    ap.add_argument("out_prefix")
    ap.add_argument("--candidate", default="hgb_nb")
    ap.add_argument("--expect-last", required=True, help="the last week the table must end with, e.g. 2026-09-21")
    ap.add_argument("--horizons", type=int, nargs="+", default=list(range(1, 9)))
    ap.add_argument("--shift", type=int, default=4)
    a = ap.parse_args()

    codes, Y, dates, pop = ev.load_wide(a.table, "bear", "weekly")
    T = Y.shape[1]
    if str(dates[-1]) != a.expect_last:
        raise SystemExit(f"the table ends at {dates[-1]}, expected {a.expect_last}: the freeze would use the wrong data")
    pairs = pd.read_parquet(a.adjacency)[["code5_a", "code5_b"]].itertuples(index=False, name=None)
    W = ev.adjacency_matrix(pairs, codes)

    o = T - 1
    rows = forecast_rows(Y, dates, pop, codes, W, o, a.horizons, a.candidate)
    o2 = o - a.shift
    rows += forecast_rows(Y, dates, pop, codes, W, o2, [h + a.shift for h in a.horizons], a.candidate, "_shift4")
    df = pd.DataFrame(rows, columns=["model", "h", "origin_week", "target_week", "code5", "pred"])
    out = a.out_prefix + ".parquet"
    df.to_parquet(out)
    print(df.groupby("model").size().to_dict())
    print("target weeks:", sorted(df[df.model == a.candidate].target_week.unique()))
    print("candidate total forecast by week:", df[df.model == a.candidate].groupby("target_week").pred.sum().round(1).to_dict())
    print("naive total by week (all equal to the last week):", df[df.model == "naive"].groupby("target_week").pred.sum().round(1).to_dict())

    import sklearn

    prov = {
        "derived": True,
        "note": "Forecasts, not observations. Do not use them as counts or as training rows.",
        "frozen_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "forecast_file": out,
        "forecast_sha256": sha256(out),
        "made_by": {"scripts": {f: sha256(f) for f in ("freeze_forecast.py", "evaluate.py")}, "commit": "none: projects/ is not tracked in git"},
        "inputs": {
            "table": a.table, "table_sha256": sha256(a.table),
            "adjacency": a.adjacency, "adjacency_sha256": sha256(a.adjacency),
            "sighting": "yuiseki/akita-kumadas-wildlife-sighting@c7047ab442ea3471aaa52af6e56a966ac768ff61 (source state 2026-09-30)",
            "admin": "yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135",
        },
        "settings": {
            "candidate": a.candidate, "origin_week": str(dates[o]), "horizons": a.horizons,
            "shifted_origin_week": str(dates[o2]),
            "model": "HistGradientBoostingRegressor(loss=poisson, max_iter=150, learning_rate=0.05, max_depth=4, min_samples_leaf=40, l2_regularization=1.0, random_state=0), one model per horizon, columns with fewer than 2 distinct values dropped",
            "features": ev.FEATURES, "target": "bear reports of every kind per municipality per Monday-start week",
        },
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scikit-learn": sklearn.__version__},
        "not_checked": [
            "that reports of the last weeks of the table are complete (no registration date in the source)",
            "horizons 5 to 8 were not evaluated in the development comparison (1, 2 and 4 were)",
            "the plan's claims C2 and C3 are scored only after later reports are published",
        ],
    }
    json.dump(prov, open(a.out_prefix + ".provenance.json", "w"), indent=1, ensure_ascii=False)
    print("forecast sha256:", prov["forecast_sha256"])


if __name__ == "__main__":
    sys.exit(main())
