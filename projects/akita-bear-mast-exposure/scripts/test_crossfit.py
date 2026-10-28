"""Tests for the cross-fit offsets: no training year's B_env has seen that year's reports."""

import numpy as np

import crossfit as cf


def test_oof_train_sets_leave_the_year_out():
    for target, years in cf.OOF.items():
        assert sorted(years) == cf.BETA_YEARS[target]
        for y, train in years.items():
            assert y not in train and set(train) == set(cf.BETA_YEARS[target]) - {y}


def test_five_distinct_fits():
    assert sorted(cf.fit_sets()) == [(2023,), (2023, 2024), (2023, 2025), (2024,), (2024, 2025)]


def test_score_summary_splits_positives_and_negatives():
    s = np.array([0.1, 0.2, 0.9, 0.8])
    c = np.array([0, 0, 1, 2.0])
    d = cf.summary(s, c)
    assert d["pos"]["median"] > d["neg"]["median"] and d["auc"] == 1.0


def test_pattern():
    up = {"diff": 0.01, "lo90": 0.001}
    flat = {"diff": 0.0, "lo90": -0.001}
    big = {"beta": 0.3, "se_beta": 0.1}
    small = {"beta": 0.01, "se_beta": 0.02}
    orig = {2025: 0.007, 2026: 0.007}
    assert cf.pattern({2025: up, 2026: up}, {2025: small, 2026: small}, orig) == "C"
    assert cf.pattern({2025: flat, 2026: up}, {2025: big, 2026: small}, orig) == "B"
    assert cf.pattern({2025: flat, 2026: flat}, {2025: small, 2026: small}, orig) == "A"
