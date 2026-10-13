"""Forecast many series h steps ahead from rolling origins, and score each model by horizon.

For each origin o (the last --origins positions from which --horizons steps still lie in the data,
or --origin-from onward), every model gets the history up to and including o and forecasts
o+1 .. o+H. Nothing after o reaches a model. Scores: MAE, RMSE and bias (mean of forecast minus
actual) overall and per horizon.

Models
    series (fitted on one series' history):
      naive               the last value
      seasonal_naive      the value one whole number of seasons back
      climatology         the mean of the history's values in the same phase of the season
      ets                 Holt-Winters, additive trend and season (statsmodels)
    pooled (fitted on all series' history before the origin, then applied to each series):
      shrunk_persistence  y[o+h] = a + b * y[o], a and b fitted by least squares per horizon:
                          the last value pulled towards the mean as far as the data say
      shrunk_to_own_mean  y[o+h] = m_s + b * (y[o] - m_s), m_s the series' own mean so far and b
                          fitted on all series' deviations: pulled towards its own level
      lag_gbdt            histogram gradient boosting on the last `season` values and the phase,
                          one model per horizon

Series must be regular (one value per period, no gaps) and aligned so that index 0 has phase 0.

Usage:
    uvx --with numpy --with scipy --with scikit-learn --with statsmodels --with duckdb python forecast.py \
        TABLE SERIES_COL TIME_COL VALUE_COL --season 12 --horizons 12 --origins 24 \
        --models naive seasonal_naive climatology shrunk_persistence ets lag_gbdt
"""

import argparse
import warnings

import numpy as np


def naive(history, h, season, train):
    return np.full(h, history[-1])


def seasonal_naive(history, h, season, train):
    n = len(history)
    steps = np.arange(1, h + 1)
    back = season * np.ceil(steps / season).astype(int)
    return history[n - 1 + steps - back]


def climatology(history, h, season, train):
    n = len(history)
    phase = np.arange(n) % season
    return np.array([history[phase == (n - 1 + k) % season].mean() for k in range(1, h + 1)])


def ets(history, h, season, train):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    if len(history) < 2 * season + 1:
        raise SystemExit(f"ets needs at least {2 * season + 1} periods of history")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(history, trend="add", seasonal="add",
                                   seasonal_periods=season).fit()
    return np.asarray(fit.forecast(h))


def _pairs(series, o, h, lags=1, season=None):
    """Training rows from every series: features at time t (t <= o - h), target at t + h."""
    X, y = [], []
    for s in series.values():
        for t in range(lags - 1, o - h + 1):
            feats = list(s[t - lags + 1:t + 1][::-1])
            if season:
                feats.append(t % season)
            X.append(feats)
            y.append(s[t + h])
    return np.array(X, float), np.array(y, float)


def shrunk_persistence(series, o, h, season):
    X, y = _pairs(series, o, h)
    b, a = np.polyfit(X[:, 0], y, 1)
    return {k: a + b * s[o] for k, s in series.items()}


def shrunk_to_own_mean(series, o, h, season):
    """y[o+h] = m_s + b * (y[o] - m_s), where m_s is the series' own mean up to o and b is fitted
    on all series' deviations from their own means (pairs with t + h <= o)."""
    xs, ys, means = [], [], {}
    for k, s in series.items():
        m = s[:o + 1].mean()
        means[k] = m
        t = np.arange(0, o - h + 1)
        xs.append(s[t] - m)
        ys.append(s[t + h] - m)
    x, y = np.concatenate(xs), np.concatenate(ys)
    b = float(x @ y / (x @ x)) if (x @ x) > 0 else 0.0
    return {k: means[k] + b * (s[o] - means[k]) for k, s in series.items()}


def lag_gbdt(series, o, h, season):
    from sklearn.ensemble import HistGradientBoostingRegressor

    X, y = _pairs(series, o, h, lags=season, season=season)
    model = HistGradientBoostingRegressor(random_state=0).fit(X, y)
    rows = {k: list(s[o - season + 1:o + 1][::-1]) + [o % season] for k, s in series.items()}
    pred = model.predict(np.array(list(rows.values()), float))
    return dict(zip(rows, pred))


MODELS = {
    "naive": {"kind": "series", "fn": naive},
    "seasonal_naive": {"kind": "series", "fn": seasonal_naive},
    "climatology": {"kind": "series", "fn": climatology},
    "ets": {"kind": "series", "fn": ets},
    "shrunk_persistence": {"kind": "pooled", "fn": shrunk_persistence},
    "shrunk_to_own_mean": {"kind": "pooled", "fn": shrunk_to_own_mean},
    "lag_gbdt": {"kind": "pooled", "fn": lag_gbdt},
}


def evaluate(series, models, horizons, origins, season, origin_from=None):
    series = {k: np.asarray(v, float) for k, v in series.items()}
    length = {len(v) for v in series.values()}
    if len(length) != 1:
        raise SystemExit("all series must have the same length (one value per period, no gaps)")
    (n,) = length
    last = n - 1 - horizons
    first = origin_from if origin_from is not None else last - origins + 1
    first = max(first, 0)
    origin_list = range(first, min(first + origins, last + 1))
    out = {}
    for name in models:
        m = MODELS[name]
        errs = {h: [] for h in range(1, horizons + 1)}
        for o in origin_list:
            if m["kind"] == "series":
                for s in series.values():
                    history = s[:o + 1]
                    f = m["fn"](history.copy(), horizons, season, None)
                    for h in range(1, horizons + 1):
                        errs[h].append(f[h - 1] - s[o + h])
            else:
                for h in range(1, horizons + 1):
                    hist = {k: s[:o + 1] for k, s in series.items()}
                    f = m["fn"](hist, o, h, season)
                    for k, s in series.items():
                        errs[h].append(f[k] - s[o + h])
        all_e = np.concatenate([np.array(v) for v in errs.values()])
        out[name] = {
            "n": len(all_e), "mae": float(np.abs(all_e).mean()),
            "rmse": float(np.sqrt((all_e ** 2).mean())), "bias": float(all_e.mean()),
            "by_horizon": {h: {"n": len(v), "mae": float(np.abs(v).mean()),
                               "bias": float(np.mean(v))} for h, v in errs.items()},
        }
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("series")
    p.add_argument("time")
    p.add_argument("value")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--horizons", type=int, default=1)
    p.add_argument("--origins", type=int, default=12)
    p.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    p.add_argument("--report-horizons", type=int, nargs="*", default=[])
    a = p.parse_args()

    import duckdb

    rows = duckdb.sql(f'select "{a.series}", "{a.time}", "{a.value}" from \'{a.table}\' '
                      f'order by 1, 2').fetchall()
    series, times = {}, {}
    for k, t, v in rows:
        if v is None:
            raise SystemExit(f"series {k} has a missing value at {t}; fill or drop it first")
        series.setdefault(k, []).append(v)
        times.setdefault(k, []).append(t)
    if len({tuple(v) for v in times.values()}) != 1:
        raise SystemExit("every series must cover the same periods")
    print(f"series {len(series)}, periods {len(next(iter(times.values())))}, season {a.season}, "
          f"horizons 1..{a.horizons}, origins {a.origins}")
    res = evaluate(series, a.models, a.horizons, a.origins, a.season)
    base = res.get("seasonal_naive") or res.get("naive")
    for name, r in res.items():
        rel = f", MAE / {('seasonal_naive' if 'seasonal_naive' in res else 'naive')} {r['mae'] / base['mae']:.3f}" if base else ""
        print(f"{name:<19} n {r['n']}  MAE {r['mae']:.4g}  RMSE {r['rmse']:.4g}  bias {r['bias']:+.4g}{rel}")
        for h in a.report_horizons:
            b = r["by_horizon"][h]
            print(f"    h={h}: MAE {b['mae']:.4g}, bias {b['bias']:+.4g}")


if __name__ == "__main__":
    main()
