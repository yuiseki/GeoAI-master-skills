"""Tests for score_frozen: the C2 and C3 decision rules of EXPERIMENT_PLAN.md (B5), on made-up forecasts."""

import numpy as np
import pandas as pd

import score_frozen as sf


def make(frozen_err, naive_err, weeks=8, m=10, seed=0, good_ranking=True):
    rng = np.random.default_rng(seed)
    codes = [f"c{i}" for i in range(m)]
    level = np.linspace(5, 0.5, m)
    fc, act = [], []
    for w in range(weeks):
        week = str(np.datetime64("2026-09-28") + np.timedelta64(7 * w, "D"))
        y = rng.poisson(level * 3).astype(float)
        for i, c in enumerate(codes):
            act.append((c, week, y[i]))
            noise = rng.normal(0, 1, size=3)
            fc.append(("cand", w + 1, week, c, max(0.0, y[i] + frozen_err * noise[0])))
            fc.append(("naive", w + 1, week, c, max(0.0, y[i] + naive_err * noise[1])))
            fc.append(("muni_mean", w + 1, week, c, float(level[i] * 3) if good_ranking else float(level[::-1][i] * 3)))
    forecast = pd.DataFrame(fc, columns=["model", "h", "target_week", "code5", "pred"])
    actual = pd.DataFrame(act, columns=["code5", "target_week", "actual"])
    return forecast, actual


def test_weekly_mae_pairs_forecasts_with_actuals_and_stops_on_missing_actuals():
    fc, ac = make(0.5, 3.0)
    t = sf.weekly_mae(fc, ac)
    assert set(t.model) == {"cand", "naive", "muni_mean"} and t.target_week.nunique() == 8
    try:
        sf.weekly_mae(fc, ac.iloc[:-5])
        raise AssertionError("should have stopped")
    except ValueError:
        pass


def test_c2_supported_when_the_candidate_beats_naive_with_an_interval_below_zero():
    fc, ac = make(0.2, 4.0)
    res = sf.decide(fc, ac, B=500, seed=0)
    assert res["C2"]["decision"] == "supported"
    assert res["C2"]["diff"] < 0 and res["C2"]["hi"] < 0


def test_c2_rejected_when_the_candidate_is_clearly_worse():
    fc, ac = make(4.0, 0.2)
    assert sf.decide(fc, ac, B=500, seed=0)["C2"]["decision"] == "rejected"


def test_c2_undetermined_when_the_two_are_alike():
    fc, ac = make(1.0, 1.0)
    assert sf.decide(fc, ac, B=500, seed=0)["C2"]["decision"] == "undetermined"


def test_capture_is_the_share_of_reports_in_the_top_five_and_c3_compares_with_the_static_ranking():
    fc, ac = make(0.1, 1.0, good_ranking=False)  # the static ranking is reversed, so it should lose
    res = sf.decide(fc, ac, B=500, seed=0)
    assert res["C3"]["diff"] > 0
    assert 0 <= res["C3"]["candidate_capture"] <= 1


def test_as_actuals_reads_the_weekly_table_of_build_table():
    import datetime as dt

    wk = pd.DataFrame({"code5": ["a", "b"], "week_start": [dt.date(2026, 9, 28), dt.date(2026, 9, 28)], "bear": [3, 0], "bear_sight": [2, 0]})
    out = sf.as_actuals(wk)
    assert list(out.columns) == ["code5", "target_week", "actual"]
    assert list(out.target_week) == ["2026-09-28", "2026-09-28"] and list(out.actual) == [3, 0]
    # the already-converted form passes through
    assert sf.as_actuals(out).equals(out)
