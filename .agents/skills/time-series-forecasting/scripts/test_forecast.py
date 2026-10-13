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
    # Every series jumps from 0 to 100 at t=60; forecasts for t=41..50 must not know it.
    rng = np.random.default_rng(4)
    series = {f"s{i}": np.r_[rng.normal(size=60), 100 + rng.normal(size=20)] for i in range(5)}
    r = evaluate(series, ["shrunk_to_own_mean"], horizons=1, origins=10, season=12, origin_from=40)
    assert r["shrunk_to_own_mean"]["mae"] < 2
