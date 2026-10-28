"""Tests for fitting one model for one target year and scoring it."""

import numpy as np

import evaluate as ev


def toy(n=50_000, seed=0, beta=0.5):
    rng = np.random.default_rng(seed)
    benv = 1 / (1 + np.exp(-rng.normal(-5, 1.5, n)))
    e = rng.random(n)
    s = {2023: 4.9, 2024: 2.4, 2025: 5.0}
    counts = {}
    for t in s:
        eta = np.log(benv / (1 - benv)) + beta * s[t] * e
        counts[t] = (rng.random(n) < 1 / (1 + np.exp(-eta))).astype(float)
    return benv, e, s, counts


def test_run_fits_on_training_years_and_ranks_the_target():
    benv, e, s, counts = toy()
    r = ev.run(benv, e, s, counts, train=[2023, 2024], target=2025)
    assert r["fit"]["beta"] > 0.3
    m0 = ev.metrics(benv, counts[2025])
    assert r["metrics"]["capture@5%"] > m0["capture@5%"]


def test_run_does_not_read_the_target_year_for_fitting():
    benv, e, s, counts = toy()
    a = ev.run(benv, e, s, counts, train=[2023, 2024], target=2025)
    counts2 = dict(counts)
    counts2[2025] = np.zeros_like(counts[2025])
    counts2[2025][:10] = 1
    b = ev.run(benv, e, s, counts2, train=[2023, 2024], target=2025, score_only=True)
    assert a["fit"] == b["fit"]


def test_metrics_reports_weighted_capture():
    score = np.array([3.0, 2.0, 1.0, 0.0] * 5)
    c = np.array([2.0, 0, 0, 1] * 5)
    m = ev.metrics(score, c)
    assert 0 <= m["capture@5%_reports"] <= 1 and m["n_pos"] == 10


def test_radius_choice_prefers_2km_on_a_tie():
    import run_dev

    assert run_dev.choose(0.5005, 0.5) == "2000"
    assert run_dev.choose(0.52, 0.50) == "500"
    assert run_dev.choose(0.50, 0.52) == "2000"


def test_judge():
    import run_confirm

    up, flat = {"diff": 0.01, "lo90": 0.001}, {"diff": 0.01, "lo90": -0.001}
    assert run_confirm.judge(up, up) == "supported"
    assert run_confirm.judge(up, flat) == "mixed / not confirmed"
    assert run_confirm.judge(flat, flat) == "not supported"
