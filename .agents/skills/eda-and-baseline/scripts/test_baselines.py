"""uvx --with duckdb --with scikit-learn --with pytest pytest test_baselines.py"""

import numpy as np
import pytest

from baselines import evaluate


def make(n=200, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    group = np.array([f"g{i % 20}" for i in range(n)])
    y = 2.0 * x + rng.normal(scale=0.5, size=n)
    return {"x": x, "group": group, "y": y}


def test_linear_beats_constant_on_a_linear_target():
    d = make()
    s = evaluate(d["y"], np.c_[d["x"]], d["group"], folds=5, group_folds=False, seed=0)
    assert s["linear"]["r2"] > 0.9
    assert s["mean"]["r2"] < 0.05
    assert s["median"]["r2"] < 0.05


def test_group_mean_uses_training_rows_only():
    # Every group has one row whose target is unrelated to the rest of the group. If the group
    # mean were taken over all rows, it would contain each test row's own target and look good.
    rng = np.random.default_rng(1)
    group = np.array([f"g{i}" for i in range(100) for _ in range(2)])
    y = rng.normal(size=200)
    s = evaluate(y, np.c_[np.zeros(200)], group, folds=2, group_folds=False, seed=0)
    assert s["group_mean"]["r2"] < 0.1


def test_group_folds_keep_each_group_on_one_side():
    d = make()
    s = evaluate(d["y"], np.c_[d["x"]], d["group"], folds=5, group_folds=True, seed=0)
    # With whole groups held out, no training row shares the test row's group, so the group mean
    # falls back to the overall training mean.
    assert s["group_mean"]["r2"] == pytest.approx(s["mean"]["r2"], abs=1e-9)


def test_every_row_gets_one_out_of_fold_prediction():
    d = make(n=53)
    s = evaluate(d["y"], np.c_[d["x"]], d["group"], folds=5, group_folds=False, seed=0)
    assert s["mean"]["n"] == 53
