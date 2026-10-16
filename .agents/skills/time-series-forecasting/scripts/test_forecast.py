"""uvx --with numpy --with scipy --with scikit-learn --with statsmodels --with duckdb --with pytest pytest test_forecast.py"""

import numpy as np
import pytest

from forecast import MODELS, evaluate


def panel(n_series=5, length=120, season=12, trend=0.0, noise=0.3, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(length)
    return {f"s{i}": (10 + 3 * np.sin(2 * np.pi * t / season) + trend * t
                      + rng.normal(scale=noise, size=length)) for i in range(n_series)}


def test_models_see_only_the_history_up_to_each_origin():
    seen = []

    def spy(history, h, season, train):
        seen.append(len(history))
        return np.full(h, history[-1])

    MODELS["spy"] = {"kind": "series", "fn": spy}
    try:
        series = {"a": np.arange(60, dtype=float)}
        r = evaluate(series, ["spy"], horizons=3, origins=10, season=12)
        # Origins are the last 10 points from which 3 steps ahead still lie in the data.
        assert sorted(set(seen)) == list(range(60 - 3 - 10 + 1, 60 - 3 + 1))
        assert r["spy"]["n"] == 10 * 3
    finally:
        del MODELS["spy"]


def test_seasonal_naive_beats_naive_on_a_seasonal_series():
    r = evaluate(panel(), ["naive", "seasonal_naive"], horizons=6, origins=24, season=12)
    assert r["seasonal_naive"]["mae"] < 0.6 * r["naive"]["mae"]


def test_seasonal_naive_reaches_back_whole_seasons_beyond_one_cycle():
    # Exact seasonal pattern with no noise: seasonal naive is perfect at every horizon up to 24.
    t = np.arange(96)
    series = {"a": np.sin(2 * np.pi * t / 12)}
    r = evaluate(series, ["seasonal_naive"], horizons=24, origins=6, season=12)
    assert r["seasonal_naive"]["mae"] == pytest.approx(0.0, abs=1e-9)


def test_climatology_is_biased_under_a_trend_and_ets_is_not():
    r = evaluate(panel(trend=0.05), ["climatology", "ets"], horizons=1, origins=24, season=12)
    assert r["climatology"]["bias"] < -1.0  # the past mean is too low when values rise
    assert abs(r["ets"]["bias"]) < 0.3
    assert r["ets"]["mae"] < r["climatology"]["mae"]


def test_pooled_models_are_fitted_on_training_periods_only():
    # Every series jumps by +50 after time 100. A pooled model that saw the test periods would
    # learn the jump; one fitted on the history before each origin cannot.
    rng = np.random.default_rng(1)
    series = {f"s{i}": np.r_[rng.normal(size=100), 50 + rng.normal(size=20)] for i in range(10)}
    r = evaluate(series, ["shrunk_persistence", "lag_gbdt"], horizons=1, origins=5, season=12,
                 origin_from=95)
    # Origins 95..99 forecast 96..100; only the forecast of t=100 crosses the jump.
    assert r["shrunk_persistence"]["by_horizon"][1]["n"] == 50
    assert r["lag_gbdt"]["mae"] > 5  # it could not know the jump is coming


def test_results_by_horizon():
    r = evaluate(panel(), ["naive"], horizons=3, origins=10, season=12)
    assert sorted(r["naive"]["by_horizon"]) == [1, 2, 3]
    assert all(v["n"] == 5 * 10 for v in r["naive"]["by_horizon"].values())


def test_climatology_matches_the_phase_of_the_season():
    t = np.arange(96)
    series = {"a": np.sin(2 * np.pi * t / 12)}
    r = evaluate(series, ["climatology"], horizons=12, origins=6, season=12)
    assert r["climatology"]["mae"] == pytest.approx(0.0, abs=1e-9)


def test_shrinking_to_each_series_own_mean_removes_the_pooled_bias():
    # Series at very different levels, each noisy around its own level.
    rng = np.random.default_rng(3)
    series = {f"s{i}": level + rng.normal(scale=1.0, size=80) for i, level in enumerate([0, 5, 20, 50])}
    r = evaluate(series, ["shrunk_persistence", "shrunk_to_own_mean", "naive"], horizons=1,
                 origins=20, season=12)
    pooled, own = r["shrunk_persistence"], r["shrunk_to_own_mean"]
    assert own["mae"] < pooled["mae"]
    assert own["mae"] < r["naive"]["mae"]  # pulling a noisy last value to its own mean helps


def test_own_mean_uses_only_the_history():
    from forecast import shrunk_to_own_mean

    # The future (from t=6) jumps; the forecast from o=5 must be built from t <= 5 only.
    series = {"a": np.array([1.0, 3.0, 1.0, 3.0, 1.0, 3.0, 100.0, 100.0]),
              "b": np.array([10.0, 12.0, 10.0, 12.0, 10.0, 12.0, 500.0, 500.0])}
    o, h = 5, 1
    means = {"a": 2.0, "b": 11.0}  # means of t = 0..5
    x = np.r_[[series[k][:o] - means[k] for k in series]].ravel()       # t = 0..4
    y = np.r_[[series[k][1:o + 1] - means[k] for k in series]].ravel()  # t + 1 = 1..5
    b = x @ y / (x @ x)
    f = shrunk_to_own_mean({k: v[:o + 1] for k, v in series.items()}, o, h, 12)
    for k in series:
        assert f[k] == pytest.approx(means[k] + b * (series[k][o] - means[k]))
    # Handing it the whole series must not change the answer: it may read only up to o.
    g = shrunk_to_own_mean(series, o, h, 12)
    assert g == pytest.approx(f)


def test_the_break_report_names_a_series_with_a_level_jump_and_says_so_when_there_is_none():
    from forecast import break_report

    rng = np.random.default_rng(0)
    series = {f"s{i}": 100.0 * (1 + i) * np.exp(0.01 * np.arange(60) + rng.normal(scale=0.005, size=60))
              for i in range(4)}
    times = list(range(60))
    assert any("no level jumps" in line for line in break_report(series, times))
    series["s2"][30:] = series["s2"][30:] * 1.6
    assert any("s2" in line and "30" in line for line in break_report(series, times))


# SARIMA. statsmodels does the fitting (a Kalman filter); the checks below compute the same forecasts another way.

def test_sarima_without_parameters_is_naive_and_seasonal_naive():
    from forecast import sarima_fit

    rng = np.random.default_rng(4)
    y = 10 + np.cumsum(rng.normal(size=80))
    f = sarima_fit(y, 12, (0, 1, 0), (0, 0, 0)).forecast(5)
    assert np.allclose(f, y[-1])
    s = np.sin(2 * np.pi * np.arange(96) / 12) + rng.normal(scale=0.2, size=96)
    f = sarima_fit(s, 12, (0, 0, 0), (0, 1, 0)).forecast(24)
    assert np.allclose(f, MODELS["seasonal_naive"]["fn"](s, 24, 12, None))


def test_arima_011_forecast_is_simple_exponential_smoothing():
    # y_t - y_(t-1) = e_t + theta e_(t-1) gives the same forecast as the level l_t = a y_t + (1 - a) l_(t-1) with
    # a = 1 + theta; the recursion below is written by hand, not taken from statsmodels.
    from forecast import sarima_fit

    rng = np.random.default_rng(5)
    e = rng.normal(size=401)
    y = 50 + np.cumsum(e[1:] - 0.6 * e[:-1])
    fit = sarima_fit(y, 12, (0, 1, 1), (0, 0, 0))
    a = 1 + fit.params[0]
    assert a == pytest.approx(0.4, abs=0.08)
    level = y[0]
    for v in y[1:]:
        level = a * v + (1 - a) * level
    assert fit.forecast(3) == pytest.approx(np.full(3, level), abs=1e-6)


def _simulate_sarima(rng, n, phi=0.6, big_theta=-0.5, season=12):
    # (1 - phi L)(1 - L^12) y_t = (1 + Theta L^12) e_t
    e = rng.normal(size=n + 200)
    w = np.zeros(n + 200)
    for t in range(n + 200):
        w[t] = e[t] + (big_theta * e[t - season] if t >= season else 0) + (phi * w[t - 1] if t else 0)
    y = np.zeros(n + 200)
    for t in range(n + 200):
        y[t] = w[t] + (y[t - season] if t >= season else 0)
    return y[200:]


def test_sarima_recovers_simulated_coefficients():
    from forecast import sarima_fit

    est = []
    for s in range(8):
        y = _simulate_sarima(np.random.default_rng(10 + s), 240)
        est.append(sarima_fit(y, 12, (1, 0, 0), (0, 1, 1)).params[:2])
    phi, big_theta = np.mean(est, axis=0)
    assert phi == pytest.approx(0.6, abs=0.06)
    assert big_theta == pytest.approx(-0.5, abs=0.1)


def test_seasonal_differencing_of_a_fixed_season_drives_the_seasonal_ma_to_minus_one():
    # A fixed seasonal pattern plus white noise needs no seasonal difference. Differencing anyway leaves
    # (1 - L^12) e_t, a seasonal MA with Theta = -1: the fit runs to the edge, and the forecast becomes the
    # seasonal mean of the history (climatology), not the last season.
    from forecast import sarima_fit

    rng = np.random.default_rng(6)
    y = 10 + 3 * np.sin(2 * np.pi * np.arange(240) / 12) + rng.normal(size=240)
    fit = sarima_fit(y, 12, (0, 0, 0), (0, 1, 1))
    assert fit.params[0] < -0.85
    clim = MODELS["climatology"]["fn"](y, 12, 12, None)
    last = MODELS["seasonal_naive"]["fn"](y, 12, 12, None)
    f = fit.forecast(12)
    assert np.abs(f - clim).mean() < 0.3 * np.abs(f - last).mean()


def test_sarima_beats_naive_and_climatology_on_a_trending_seasonal_panel():
    r = evaluate(panel(n_series=3, trend=0.05), ["naive", "climatology", "sarima"], horizons=6, origins=6,
                 season=12)
    assert r["sarima"]["mae"] < 0.5 * min(r["naive"]["mae"], r["climatology"]["mae"])
    assert abs(r["sarima"]["bias"]) < 0.2


def test_sarima_stops_on_a_short_history():
    from forecast import sarima

    with pytest.raises(SystemExit):
        sarima(np.arange(20, dtype=float), 3, 12, None)
