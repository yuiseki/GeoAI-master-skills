"""Tests of scripts/flood.py on small examples whose answers are known.

uvx --with numpy --with scipy --with scikit-image --with pytest pytest -q scripts/test_flood.py
"""
import numpy as np
import pytest

import flood


def test_boxcar_mean_ignores_nan():
    a = np.ones((5, 5))
    a[2, 2] = np.nan
    a[0, 0] = 10.0
    b = flood.boxcar(a, 3)
    assert b[2, 2] == pytest.approx(1.0)  # 8 valid neighbours, all 1
    assert b[0, 0] == pytest.approx((10 + 1 + 1 + 1) / 4)  # corner sees 4 pixels
    assert flood.boxcar(a, 1)[0, 0] == 10.0  # k = 1 is no smoothing


def test_boxcar_all_nan_stays_nan():
    a = np.full((3, 3), np.nan)
    assert np.isnan(flood.boxcar(a, 3)).all()


def test_ratio_db():
    assert flood.ratio_db(np.array([0.5]), np.array([1.0]))[0] == pytest.approx(-3.0103, abs=1e-4)
    assert flood.ratio_db(np.array([2.0]), np.array([1.0]))[0] == pytest.approx(3.0103, abs=1e-4)


def test_standardized_rate_reweights_by_target_classes():
    # reference: class 1 rate 0.1 (2000 px), class 2 rate 0.5 (2000 px). target: all class 2.
    cls = np.array([1] * 2000 + [2] * 2000 + [2] * 10)
    flag = np.array([1] * 200 + [0] * 1800 + [1] * 1000 + [0] * 1000 + [0] * 10, bool)
    ref = np.array([True] * 4000 + [False] * 10)
    tgt = ~ref
    r = flood.standardized_rate(flag, cls, tgt, ref, min_n=1000)
    assert r["rate"] == pytest.approx(0.5)
    assert r["dropped_share"] == 0.0
    tgt2 = np.zeros_like(ref)
    tgt2[:2000:2] = True  # 1000 target pixels of class 1
    tgt2[2000:3000:2] = True  # 500 of class 2
    r2 = flood.standardized_rate(flag, cls, tgt2, ref & ~tgt2, min_n=500)
    # taking the target out of ref leaves class 1 at 100 / 1000 = 0.1 and class 2 at 500 / 1500 (the flagged evens left)
    assert r2["class_rates"] == {1: pytest.approx(0.1), 2: pytest.approx(1 / 3)}
    assert r2["rate"] == pytest.approx((1000 * 0.1 + 500 / 3) / 1500)


def test_standardized_rate_drops_small_reference_classes():
    cls = np.array([1] * 2000 + [3] * 50 + [1] * 30 + [3] * 70)
    flag = np.zeros(cls.size, bool)
    flag[:1000] = True  # class 1 reference rate 0.5
    ref = np.zeros(cls.size, bool)
    ref[:2050] = True
    tgt = ~ref  # 30 of class 1, 70 of class 3
    r = flood.standardized_rate(flag, cls, tgt, ref, min_n=1000)
    assert r["rate"] == pytest.approx(0.5)
    assert r["dropped_share"] == pytest.approx(0.7)
    assert r["dropped_classes"] == [3]


def test_components_8_connected():
    m = np.zeros((4, 4), bool)
    m[0, 0] = m[1, 1] = True  # diagonal: one component
    m[3, 3] = True
    lab = flood.components(m)
    assert lab[0, 0] == lab[1, 1] != lab[3, 3]
    assert lab[2, 0] == 0
    assert len(set(lab[m])) == 2


def test_block_ids():
    x = np.array([0.0, 999.0, 1000.0, 2500.0])
    y = np.array([0.0, 0.0, 0.0, 1500.0])
    b = flood.block_ids(x, y, 1000)
    assert b[0] == b[1] != b[2]
    assert len(set(b)) == 3


def test_unit_bootstrap_interval_covers_rate():
    rng = np.random.default_rng(1)
    units = np.repeat(np.arange(200), 50)
    flag = rng.random(units.size) < 0.3
    lo, hi = flood.bootstrap_rate(flag, units, n=500, seed=0)
    assert lo < flag.mean() < hi
    assert hi - lo < 0.1


def test_bootstrap_ratio_of_two_groups():
    rng = np.random.default_rng(2)
    u1, u2 = np.repeat(np.arange(100), 20), np.repeat(np.arange(100), 20)
    f1, f2 = rng.random(u1.size) < 0.4, rng.random(u2.size) < 0.1
    lo, hi = flood.bootstrap_ratio(f1, u1, f2, u2, n=500, seed=0)
    assert lo < 4.0 < hi


def test_lift():
    flag = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0], bool)
    in_a = np.array([1, 1, 1, 0, 0, 0, 0, 0, 0, 0], bool)
    pop = np.ones(10, bool)
    # 3 of 4 flagged in A (0.75); A is 0.3 of the population -> 2.5
    assert flood.lift(flag, in_a, pop) == pytest.approx(2.5)


def test_shift_against_mask_recovers_known_shift():
    rng = np.random.default_rng(3)
    water = np.zeros((200, 200), bool)
    water[60:90, 40:160] = True
    water[120:180, 100:130] = True
    db = np.where(water, -22.0, -8.0) + rng.normal(0, 1.0, water.shape)
    shifted = np.roll(np.roll(db, 2, axis=0), -3, axis=1)  # the image lies 2 rows down, 3 cols left of the map
    s = flood.shift_against_mask(shifted, water)
    assert s[0] == pytest.approx(-2, abs=0.3)
    assert s[1] == pytest.approx(3, abs=0.3)
    back = flood.apply_int_shift(shifted, s)
    assert np.nanmean(np.abs(back[10:-10, 10:-10] - db[10:-10, 10:-10])) < 1e-9


def test_apply_int_shift_fills_nan():
    a = np.arange(16, dtype=float).reshape(4, 4)
    b = flood.apply_int_shift(a, (1, 0))
    assert np.isnan(b[0]).all()
    assert (b[1] == a[0]).all()


def test_std_rate_draws_centre_on_the_point_value():
    rng = np.random.default_rng(4)
    units = np.repeat(np.arange(300), 40)
    cls = rng.choice([10, 50], size=units.size, p=[0.7, 0.3])
    flag = np.where(cls == 50, rng.random(units.size) < 0.2, rng.random(units.size) < 0.05)
    w = {10: 0.2, 50: 0.8}  # the target's class mix
    point = 0.2 * flag[cls == 10].mean() + 0.8 * flag[cls == 50].mean()
    d = flood.std_rate_draws(flag, cls, units, w, n=400, rng=np.random.default_rng(0))
    assert d.shape == (400,)
    assert d.mean() == pytest.approx(point, abs=0.005)
    assert np.quantile(d, 0.05) < point < np.quantile(d, 0.95)


def test_rate_draws_and_lift_draws():
    rng = np.random.default_rng(5)
    units = np.repeat(np.arange(200), 30)
    in_a = np.repeat(rng.random(200) < 0.3, 30)
    flag = np.where(in_a, rng.random(units.size) < 0.3, rng.random(units.size) < 0.1)
    d = flood.rate_draws(flag, units, n=300, rng=np.random.default_rng(0))
    assert d.mean() == pytest.approx(flag.mean(), abs=0.01)
    ld = flood.lift_draws(flag, in_a, units, n=300, rng=np.random.default_rng(0))
    pt = flood.lift(flag, in_a, np.ones_like(flag))
    assert np.quantile(ld, 0.05) < pt < np.quantile(ld, 0.95)
