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
