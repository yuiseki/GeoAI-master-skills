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
      sarima              seasonal ARIMA (statsmodels SARIMAX, maximum likelihood); the airline model
                          (0,1,1)(0,1,1)s unless --sarima-order / --sarima-seasonal say otherwise;
                          --sarima-select aic picks p, q, P, Q per origin from that origin's history
    pooled (fitted on all series' history before the origin, then applied to each series):
      shrunk_persistence  y[o+h] = a + b * y[o], a and b fitted by least squares per horizon:
                          the last value pulled towards the mean as far as the data say
      shrunk_to_own_mean  y[o+h] = m_s + b * (y[o] - m_s), m_s the series' own mean so far and b
                          fitted on all series' deviations: pulled towards its own level
      lag_gbdt            histogram gradient boosting on the last `season` values and the phase,
                          one model per horizon

Series must be regular (one value per period, no gaps) and aligned so that index 0 has phase 0.
Before any model runs, the series are checked for level jumps (series_breaks.py) and the result is printed.

Usage:
    uvx --with numpy --with scipy --with scikit-learn --with statsmodels --with duckdb python forecast.py \
        TABLE SERIES_COL TIME_COL VALUE_COL --season 12 --horizons 12 --origins 24 \
        --models naive seasonal_naive climatology shrunk_persistence ets sarima lag_gbdt \
        [--sarima-order 0 1 1 --sarima-seasonal 0 1 1 --sarima-trend n] [--origin-from 300] [--report-horizons 1 12] [--break-min-level 0]
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


SARIMA = {"order": (0, 1, 1), "seasonal": (0, 1, 1), "trend": "n", "select": None}


def sarima_select(history, season, d, D, trend="n", p_max=2, q_max=2, P_max=1, Q_max=1):
    """The (p, q, P, Q) with the smallest AIC among every combination up to the maxima, with d and D given.
    Returns the best orders, its AIC and every candidate's AIC (fits that fail are left out)."""
    import itertools

    scores = {}
    for p_, q_, P_, Q_ in itertools.product(range(p_max + 1), range(q_max + 1), range(P_max + 1), range(Q_max + 1)):
        try:
            f = sarima_fit(history, season, (p_, d, q_), (P_, D, Q_), trend)
        except Exception:
            continue
        if np.isfinite(f.aic):
            scores[(p_, q_, P_, Q_)] = float(f.aic)
    best = min(scores, key=scores.get)
    return {"order": (best[0], d, best[1]), "seasonal": (best[2], D, best[3]), "aic": scores[best], "scores": scores}


def sarima_fit(history, season, order, seasonal, trend="n"):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return SARIMAX(np.asarray(history, float), order=order, seasonal_order=(*seasonal, season),
                       trend=trend).fit(disp=False)


def sarima(history, h, season, train):
    d, D = SARIMA["order"][1], SARIMA["seasonal"][1]
    need = d + D * season + 2 * season
    if len(history) < need:
        raise SystemExit(f"sarima needs at least {need} periods of history (differences, then two seasons)")
    order, seasonal = SARIMA["order"], SARIMA["seasonal"]
    if SARIMA["select"] == "aic":  # chosen again at every origin, on the history up to it only
        sel = sarima_select(history, season, order[1], seasonal[1], SARIMA["trend"])
        order, seasonal = sel["order"], sel["seasonal"]
        SARIMA.setdefault("chosen", []).append((order, seasonal))
    return np.asarray(sarima_fit(history, season, order, seasonal, SARIMA["trend"]).forecast(h))


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
    "sarima": {"kind": "series", "fn": sarima},
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


def break_report(series, times, top=10, min_level=0.0):
    """Lines that say which series jump in level, and how the total moves, before any model is fitted."""
    from series_breaks import aggregate_breaks, find_breaks

    keys = list(series)
    values = np.array([np.asarray(series[k], float) for k in keys])
    times = list(times)
    found = find_breaks(keys, times, values, min_level=min_level)
    lines = [f"level jumps in single series (series_breaks.py): {len(found)}"]
    if not found:
        lines.append("  no level jumps found")
    for k, t, g in found[:top]:
        lines.append(f"  {k}  at {t}  {g:+.3f}  ({np.exp(g) - 1:+.1%})")
    flagged = [r for r in aggregate_breaks(values, times) if r["flag"] or r["raw_flag"]]
    for r in flagged[:top]:
        lines.append(f"  total  at {r['time']}  raw {r['raw_change']:+.3f}  like for like "
                     f"{r['like_for_like_change']:+.3f}  (entering {r['entering']}, leaving {r['leaving']})")
    if found:
        lines.append("  find out whether each jump is an event, a data revision or a change of what is counted, and say what you did about it")
    return lines


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
    p.add_argument("--origin-from", type=int, default=None,
                   help="first origin (position in the series); default: the last --origins origins")
    p.add_argument("--report-horizons", type=int, nargs="*", default=[])
    p.add_argument("--break-min-level", type=float, default=0.0,
                   help="ignore level jumps between values that are both below this (see series_breaks.py)")
    p.add_argument("--sarima-order", type=int, nargs=3, default=list(SARIMA["order"]), metavar=("p", "d", "q"))
    p.add_argument("--sarima-seasonal", type=int, nargs=3, default=list(SARIMA["seasonal"]), metavar=("P", "D", "Q"))
    p.add_argument("--sarima-trend", default=SARIMA["trend"], choices=["n", "c", "t", "ct"])
    p.add_argument("--sarima-select", choices=["aic"], help="choose p, q (0-2) and P, Q (0-1) by AIC at every "
                                                             "origin; d and D stay as given")
    a = p.parse_args()
    SARIMA.update(order=tuple(a.sarima_order), seasonal=tuple(a.sarima_seasonal), trend=a.sarima_trend,
                  select=a.sarima_select)

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
    print("\n".join(break_report(series, next(iter(times.values())), min_level=a.break_min_level)))
    res = evaluate(series, a.models, a.horizons, a.origins, a.season, a.origin_from)
    base = res.get("seasonal_naive") or res.get("naive")
    for name, r in res.items():
        rel = f", MAE / {('seasonal_naive' if 'seasonal_naive' in res else 'naive')} {r['mae'] / base['mae']:.3f}" if base else ""
        print(f"{name:<19} n {r['n']}  MAE {r['mae']:.4g}  RMSE {r['rmse']:.4g}  bias {r['bias']:+.4g}{rel}")
        for h in a.report_horizons:
            b = r["by_horizon"][h]
            print(f"    h={h}: MAE {b['mae']:.4g}, bias {b['bias']:+.4g}")
    if SARIMA.get("chosen"):
        from collections import Counter

        top = Counter(SARIMA["chosen"]).most_common(5)
        print(f"sarima orders chosen by AIC over {len(SARIMA['chosen'])} fits: "
              + ", ".join(f"{o}{s_} x{n}" for (o, s_), n in top))


if __name__ == "__main__":
    main()
