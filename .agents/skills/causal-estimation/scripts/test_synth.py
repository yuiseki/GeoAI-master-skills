"""uvx --with numpy --with scipy --with pytest pytest test_synth.py"""

import numpy as np
import pytest

from synth import placebo, synth_weights, synthetic_control


def test_an_exact_convex_combination_is_recovered():
    rng = np.random.default_rng(0)
    Y0 = rng.normal(size=(8, 4)).cumsum(0) + 10  # 8 pre periods, 4 donors
    y1 = 0.3 * Y0[:, 1] + 0.7 * Y0[:, 3]
    w = synth_weights(y1, Y0)
    assert w == pytest.approx([0, 0.3, 0, 0.7], abs=1e-6)


def test_weights_stay_on_the_simplex():
    rng = np.random.default_rng(1)
    w = synth_weights(rng.normal(size=10), rng.normal(size=(10, 6)))
    assert (w >= -1e-10).all() and w.sum() == pytest.approx(1)


def _factor_world(seed, J=20, T0=15, T=25, effect=3.0, extreme=False):
    rng = np.random.default_rng(seed)
    f = rng.normal(size=(T, 2)).cumsum(0)  # common trends
    load = rng.uniform(0, 1, (J + 1, 2))
    if extreme:
        load[0] = [2.0, 2.0]  # the treated unit's loadings lie outside the donors' range
    Y = 10 + f @ load.T + rng.normal(scale=0.3, size=(T, J + 1))
    Y[T0:, 0] += effect
    return Y[:, 0], Y[:, 1:], T0


def test_the_post_period_gap_recovers_the_effect():
    gaps = []
    for seed in range(20):
        y1, Y0, T0 = _factor_world(seed)
        r = synthetic_control(y1, Y0, T0)
        gaps.append(r["gap"][T0:].mean())
    assert np.mean(gaps) == pytest.approx(3.0, abs=0.3)


def test_a_treated_unit_outside_the_donors_fits_badly_before_treatment():
    good = synthetic_control(*_factor_world(2))
    bad = synthetic_control(*_factor_world(2, extreme=True))
    assert bad["rmspe_pre"] > 5 * good["rmspe_pre"]


def test_placebo_rank_of_a_large_effect_is_first():
    y1, Y0, T0 = _factor_world(3, effect=6.0)
    p = placebo(y1, Y0, T0)
    assert p["rank"] == 1 and p["p"] == pytest.approx(1 / 21)


def test_placebo_p_values_spread_out_without_an_effect():
    ps = [placebo(*_factor_world(100 + s, J=12, effect=0.0))["p"] for s in range(30)]
    assert 0.3 < np.mean(ps) < 0.7  # about uniform; a broken test would sit near 1 / (J + 1)


def test_too_few_pre_periods_or_donors_stop():
    with pytest.raises(SystemExit):
        synthetic_control(np.arange(5.0), np.ones((5, 3)), 1)
    with pytest.raises(SystemExit):
        synthetic_control(np.arange(5.0), np.ones((5, 1)), 3)


def test_placebos_never_use_the_treated_unit_as_a_donor():
    # Donor 0 follows the treated unit almost exactly before treatment. If the treated unit were in donor 0's
    # pool, donor 0's placebo would copy it and show the same jump, sharing first rank.
    rng = np.random.default_rng(7)
    T0, T = 12, 18
    base = rng.normal(size=T).cumsum() + 10
    y1 = base.copy()
    y1[T0:] += 5.0
    Y0 = np.c_[base + rng.normal(scale=0.01, size=T), rng.normal(size=(T, 8)).cumsum(0) + 10]
    p = placebo(y1, Y0, T0)
    assert p["rank"] == 1
    assert p["ratios"][1] < p["ratios"][0] / 10  # donor 0's own placebo has no jump to copy


def test_placebos_are_ranked_by_post_over_pre_error_not_post_error_alone():
    # One donor lies far outside the others: its own placebo fits badly before and after (a large post RMSPE
    # but a ratio near 1). Ranked by post RMSPE alone it would beat the treated unit.
    y1, Y0, T0 = _factor_world(8, J=12, effect=3.0)
    Y0[:, 0] += np.linspace(0, 40, len(y1))  # a donor drifting away from everyone
    p = placebo(y1, Y0, T0)
    assert p["rank"] == 1
