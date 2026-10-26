"""Tests for evaluate.py: causal features, baselines, and the scores."""

import numpy as np
import pytest

import evaluate as ev


def make_Y(seed=0, m=6, T=120):
    rng = np.random.default_rng(seed)
    base = rng.gamma(2.0, 1.5, size=(m, 1))
    season = 1 + 0.8 * np.sin(2 * np.pi * np.arange(T) / 52)
    return rng.poisson(base * season).astype(float)


def dates(T):
    d0 = np.datetime64("2022-04-11")
    return d0 + (7 * np.arange(T)).astype("timedelta64[D]")


@pytest.mark.parametrize("h", [1, 2, 4])
def test_features_at_t_do_not_read_after_t(h):
    Y = make_Y()
    T = Y.shape[1]
    t = 70
    Y2 = Y.copy()
    Y2[:, t + 1:] = 999.0  # garbage after the origin
    pop = np.arange(1, Y.shape[0] + 1) * 1000.0
    F1, names = ev.features(Y, dates(T), pop, h)
    F2, _ = ev.features(Y2, dates(T), pop, h)
    # every feature at t and before is the same: nothing after t reached it
    np.testing.assert_array_equal(F1[:, : t + 1], F2[:, : t + 1])


def test_seasonal_feature_looks_back_a_whole_year_from_the_target_week():
    Y = make_Y()
    T = Y.shape[1]
    pop = np.ones(Y.shape[0])
    h = 2
    F, names = ev.features(Y, dates(T), pop, h)
    j = names.index("ly")
    t = 80
    np.testing.assert_allclose(F[:, t, j], np.log1p(Y[:, t + h - 52]))
    assert np.isnan(F[:, 10, j]).all()  # before one year of history exists


def test_naive_and_seasonal_naive_baselines():
    Y = make_Y()
    o, h = 90, 3
    assert (ev.baseline(Y, o, h, "naive") == Y[:, o]).all()
    np.testing.assert_allclose(ev.baseline(Y, o, h, "seasonal_naive"), Y[:, o + h - 52])
    np.testing.assert_allclose(ev.baseline(Y, o, h, "mean_short"), Y[:, o - 3 : o + 1].mean(axis=1))


def test_models_never_see_the_future_of_the_origin():
    Y = make_Y()
    T = Y.shape[1]
    pop = np.arange(1, Y.shape[0] + 1) * 1000.0
    o, h = 90, 2
    Y2 = Y.copy()
    Y2[:, o + 1:] = 500.0
    for name in ["glm", "hgb"]:
        p1 = ev.model_forecast(name, Y, dates(T), pop, o, h)
        p2 = ev.model_forecast(name, Y2, dates(T), pop, o, h)
        np.testing.assert_allclose(p1, p2, err_msg=name)


def test_training_pairs_stop_at_the_origin():
    # the last training target is week o, so the pair (t, t+h) needs t+h <= o
    Y = make_Y()
    T = Y.shape[1]
    pop = np.ones(Y.shape[0])
    o, h = 80, 4
    X, y, w = ev.training_pairs(Y, dates(T), pop, o, h)
    assert w.max() == o - h
    assert X.shape[0] == (o - h + 1) * Y.shape[0]
    assert y.shape[0] == X.shape[0]


def test_poisson_deviance_zero_for_perfect_and_positive_otherwise():
    y = np.array([1.0, 2.0, 5.0])
    assert ev.poisson_deviance(y, y) == pytest.approx(0.0, abs=1e-9)
    assert ev.poisson_deviance(y, y + 1) > 0
    # forecasts are floored at 1e-3 for every model alike: a forecast of 0 for 0 costs only the floor
    assert ev.poisson_deviance(np.array([0.0]), np.array([0.0])) == pytest.approx(2e-3)
    # zero actual with positive prediction is defined, not NaN
    assert np.isfinite(ev.poisson_deviance(np.array([0.0]), np.array([2.0])))


def test_capture_is_one_for_the_oracle_and_less_for_a_bad_ranking():
    actual = np.array([10.0, 0, 3, 0, 1, 0, 0, 6])
    level = np.arange(8, dtype=float)
    oracle = ev.capture(actual, actual, level, k=3)
    assert oracle == pytest.approx(19 / 20)
    bad = ev.capture(-actual, actual, level, k=3)
    assert bad < oracle


@pytest.mark.parametrize("o", [52, 53, 56])
def test_hgb_at_the_first_origins_where_year_back_columns_are_degenerate(o):
    Y = make_Y(T=120)
    pop = np.arange(1, Y.shape[0] + 1) * 1000.0
    p = ev.model_forecast("hgb", Y, dates(Y.shape[1]), pop, o, 4)
    assert p.shape == (Y.shape[0],) and np.isfinite(p).all()


def test_usable_columns_drops_all_nan_and_constant_columns_and_says_which():
    X = np.array([[1.0, np.nan, 3.0, 5.0], [2.0, np.nan, 3.0, 6.0], [3.0, np.nan, 3.0, np.nan]])
    keep, dropped = ev.usable_columns(X, ["a", "b", "c", "d"])
    assert keep == [0, 3] and dropped == ["b", "c"]


def make_monthly(seed=1, m=5, T=60):
    rng = np.random.default_rng(seed)
    base = rng.gamma(2.0, 1.0, size=(m, 1))
    season = 1 + 0.8 * np.sin(2 * np.pi * np.arange(T) / 12)
    return rng.poisson(base * season).astype(float)


def month_dates(T):
    return np.datetime64("2014-04", "M") + np.arange(T)


@pytest.mark.parametrize("h", [1, 3])
def test_monthly_features_do_not_read_after_t_and_look_back_twelve_months(h):
    Y = make_monthly()
    T = Y.shape[1]
    pop = np.arange(1, Y.shape[0] + 1) * 1000.0
    t = 30
    Y2 = Y.copy()
    Y2[:, t + 1:] = 999.0
    F1, names = ev.features(Y, month_dates(T), pop, h, ev.MONTHLY)
    F2, _ = ev.features(Y2, month_dates(T), pop, h, ev.MONTHLY)
    np.testing.assert_array_equal(F1[:, : t + 1], F2[:, : t + 1])
    j = names.index("ly")
    np.testing.assert_allclose(F1[:, t, j], np.log1p(Y[:, t + h - 12]))
    assert np.isnan(F1[:, 5, j]).all()


def test_monthly_calendar_phase_is_the_target_month_not_the_origin_month():
    Y = make_monthly()
    T = Y.shape[1]
    pop = np.ones(Y.shape[0])
    F, names = ev.features(Y, month_dates(T), pop, 3, ev.MONTHLY)
    j = names.index("sin1")
    # origin index 0 is 2014-04; the target is 2014-07, so the phase is that of July
    month = 7
    expected = np.sin(2 * np.pi * (month - 0.5) / 12)
    assert F[0, 0, j] == pytest.approx(expected)


def test_monthly_baselines_use_the_period_of_the_config():
    Y = make_monthly()
    o, h = 40, 2
    np.testing.assert_allclose(ev.baseline(Y, o, h, "seasonal_naive", ev.MONTHLY), Y[:, o + h - 12])
    np.testing.assert_allclose(ev.baseline(Y, o, h, "mean_short", ev.MONTHLY), Y[:, o - 2 : o + 1].mean(axis=1))


def test_monthly_model_runs_and_never_sees_the_future():
    Y = make_monthly()
    T = Y.shape[1]
    pop = np.arange(1, Y.shape[0] + 1) * 1000.0
    o, h = 30, 2
    Y2 = Y.copy()
    Y2[:, o + 1:] = 500.0
    for name in ["glm", "hgb"]:
        p1 = ev.model_forecast(name, Y, month_dates(T), pop, o, h, ev.MONTHLY)
        p2 = ev.model_forecast(name, Y2, month_dates(T), pop, o, h, ev.MONTHLY)
        np.testing.assert_allclose(p1, p2, err_msg=name)


def test_block_bootstrap_interval_covers_a_clear_difference_and_straddles_zero_for_noise():
    rng = np.random.default_rng(0)
    blocks = np.repeat(np.arange(10), 12)
    clear = rng.normal(1.0, 0.3, size=120)
    lo, hi = ev.block_bootstrap_interval(clear, blocks, B=500, seed=0)
    assert lo > 0
    noise = rng.normal(0.0, 1.0, size=120)
    lo, hi = ev.block_bootstrap_interval(noise, blocks, B=500, seed=0)
    assert lo < 0 < hi


def test_seasonal_3y_is_the_mean_of_the_same_period_in_the_last_three_years():
    Y = make_monthly(T=80)
    o, h = 70, 2
    expected = Y[:, [o + h - 12, o + h - 24, o + h - 36]].mean(axis=1)
    np.testing.assert_allclose(ev.baseline(Y, o, h, "seasonal_3y", ev.MONTHLY), expected)


def test_seasonal_3y_uses_the_years_that_exist_and_never_the_future():
    Y = make_monthly(T=80)
    o, h = 26, 2  # only one year back (index 16) is at or before o; two years back is index 4, three is negative
    got = ev.baseline(Y, o, h, "seasonal_3y", ev.MONTHLY)
    np.testing.assert_allclose(got, Y[:, [o + h - 12, o + h - 24]].mean(axis=1))
    # an index after the origin is never used (h larger than the season would reach past o)
    assert (o + h - 12) <= o


def test_recent_year_mean_is_the_mean_of_the_last_season_of_periods_and_has_no_season_in_it():
    Y = make_monthly(T=80)
    o, h = 50, 3
    np.testing.assert_allclose(ev.baseline(Y, o, h, "recent_year", ev.MONTHLY), Y[:, o - 11 : o + 1].mean(axis=1))
    # the forecast does not depend on the horizon: it carries no season
    np.testing.assert_allclose(ev.baseline(Y, o, 1, "recent_year", ev.MONTHLY), ev.baseline(Y, o, 6, "recent_year", ev.MONTHLY))


def ring_W(m):
    """Each municipality's neighbours are the two next to it on a ring, with equal weights."""
    W = np.zeros((m, m))
    for i in range(m):
        W[i, (i - 1) % m] = W[i, (i + 1) % m] = 0.5
    return W


def test_adjacency_matrix_is_row_normalised_symmetric_in_pairs_and_stops_on_unknown_codes():
    codes = ["a", "b", "c", "d"]
    pairs = [("a", "b"), ("b", "c"), ("c", "d"), ("a", "c")]
    W = ev.adjacency_matrix(pairs, codes)
    np.testing.assert_allclose(W.sum(axis=1), 1.0)
    assert W[0, 1] > 0 and W[1, 0] > 0 and W[0, 3] == 0
    with pytest.raises(ValueError):
        ev.adjacency_matrix([("a", "zzz")], codes)
    # an isolated municipality has a zero row, not a division by zero
    W2 = ev.adjacency_matrix([("a", "b")], codes)
    assert np.isfinite(W2).all() and W2[2].sum() == 0


def test_neighbour_features_use_the_neighbours_past_only_and_the_right_neighbours():
    Y = make_Y()
    T = Y.shape[1]
    pop = np.ones(Y.shape[0])
    W = ring_W(Y.shape[0])
    t = 70
    Y2 = Y.copy()
    Y2[:, t + 1:] = 999.0
    F1, names = ev.features(Y, dates(T), pop, 2, ev.WEEKLY, W)
    F2, _ = ev.features(Y2, dates(T), pop, 2, ev.WEEKLY, W)
    np.testing.assert_array_equal(F1[:, : t + 1], F2[:, : t + 1])
    j = names.index("nb0")
    expected = np.log1p(0.5 * (Y[1, t] + Y[3, t]))  # municipality 2: neighbours 1 and 3
    assert F1[2, t, j] == pytest.approx(expected)


def test_neighbour_models_need_W_and_never_see_the_future():
    Y = make_Y()
    T = Y.shape[1]
    pop = np.arange(1, Y.shape[0] + 1) * 1000.0
    o, h = 90, 2
    with pytest.raises(ValueError):
        ev.model_forecast("hgb_nb", Y, dates(T), pop, o, h)
    W = ring_W(Y.shape[0])
    Y2 = Y.copy()
    Y2[:, o + 1:] = 500.0
    for name in ["glm_nb", "hgb_nb", "hier_hgb"]:
        p1 = ev.model_forecast(name, Y, dates(T), pop, o, h, ev.WEEKLY, W)
        p2 = ev.model_forecast(name, Y2, dates(T), pop, o, h, ev.WEEKLY, W)
        np.testing.assert_allclose(p1, p2, err_msg=name)


def test_allocate_conserves_the_total_and_falls_back_to_the_long_run_share_when_recent_is_zero():
    Y = np.array([[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]])
    Y[:, 0] = [6.0, 3.0, 1.0]  # long-run shares 0.6, 0.3, 0.1; the last 2 weeks are all zero
    out = ev.allocate(10.0, Y, recent=2)
    assert out.sum() == pytest.approx(10.0)
    np.testing.assert_allclose(out, [6.0, 3.0, 1.0])
    Y2 = np.array([[1.0, 8.0], [3.0, 2.0]])  # the last week shares are 0.8 and 0.2
    np.testing.assert_allclose(ev.allocate(5.0, Y2, recent=1), [4.0, 1.0])


def test_load_wide_orders_municipalities_and_weeks_and_keeps_zeros(tmp_path):
    import pandas as pd

    rows = []
    for code, pop in (("b", 200.0), ("a", 100.0)):  # deliberately out of order
        for k in range(3):
            rows.append((code, np.datetime64("2022-04-11") + np.timedelta64(7 * k, "D"), k + (10 if code == "b" else 0), pop))
    pd.DataFrame(rows, columns=["code5", "week_start", "bear", "population"]).to_parquet(tmp_path / "t.parquet")
    codes, Y, dates, pop = ev.load_wide(str(tmp_path / "t.parquet"), "bear", "weekly")
    assert codes == ["a", "b"]
    np.testing.assert_array_equal(Y, [[0, 1, 2], [10, 11, 12]])
    assert dates[0] == np.datetime64("2022-04-11") and dates[2] == np.datetime64("2022-04-25")
    np.testing.assert_array_equal(pop, [100.0, 200.0])
