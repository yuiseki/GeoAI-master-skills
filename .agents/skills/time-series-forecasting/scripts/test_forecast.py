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
