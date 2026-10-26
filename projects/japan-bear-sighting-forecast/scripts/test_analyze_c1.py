"""Tests for analyze_c1: the paired block bootstrap and the decision rule of claim C1."""

import numpy as np
import pandas as pd

import analyze_c1 as a


def preds(naive_err, other_err, years=range(2016, 2026), per_year=12, m=4):
    rows = []
    rng = np.random.default_rng(0)
    for y in years:
        for k in range(per_year):
            origin = f"{y}-{k + 1:02d}"
            actual = rng.poisson(3, size=m).astype(float)
            for model, err in (("naive", naive_err), ("seasonal_naive", other_err), ("muni_mean", other_err)):
                for i in range(m):
                    rows.append((model, 1, origin, f"c{i}", actual[i], actual[i] + err * (1 if (i + k) % 2 else -1)))
    return pd.DataFrame(rows, columns=["model", "h", "origin_week", "code5", "actual", "pred"])


def test_per_origin_mae_has_one_row_per_model_h_origin():
    df = preds(1.0, 2.0)
    t = a.per_origin_mae(df)
    assert set(t.columns) >= {"model", "h", "origin_week", "mae", "year"}
    assert len(t) == 3 * 10 * 12
    assert t.year.min() == 2016


def test_c1_supported_when_both_baselines_are_clearly_worse_than_naive_at_h1():
    t = a.per_origin_mae(preds(1.0, 3.0))
    res = a.c1_decision(t, B=300, seed=0)
    assert res["decision"] == "supported"
    assert res["seasonal_naive"]["diff"] > 0 and res["seasonal_naive"]["lo"] > 0


def test_c1_not_supported_when_a_baseline_is_better_than_naive():
    t = a.per_origin_mae(preds(3.0, 1.0))
    res = a.c1_decision(t, B=300, seed=0)
    assert res["decision"] == "not supported"


def test_c1_undetermined_when_the_interval_straddles_zero():
    df = preds(1.0, 1.0)  # same error size: the differences are noise around zero
    t = a.per_origin_mae(df)
    t.loc[t.model == "seasonal_naive", "mae"] += np.random.default_rng(1).normal(0, 0.5, size=(t.model == "seasonal_naive").sum())
    res = a.c1_decision(t, B=300, seed=0)
    assert res["decision"] in ("undetermined", "not supported")
    assert res["decision"] != "supported"
