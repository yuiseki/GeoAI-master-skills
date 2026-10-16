"""uvx --with numpy --with pytest pytest test_did.py"""

import numpy as np
import pytest

from did import aggregate, att_gt, two_by_two, twfe


def test_two_by_two_by_hand():
    # Group means: treated 10 -> 18, control 5 -> 9: (18 - 10) - (9 - 5) = 4.
    y = np.array([10.0, 18, 5, 9])
    g = np.array([1, 1, 0, 0])
    post = np.array([0, 1, 0, 1])
    assert two_by_two(y, g, post)["did"] == pytest.approx(4)


def _panel(seed=0, n_per=40, periods=10, cohorts=(4, 6, 8), effect=lambda e: 1.0, trend=None, noise=0.5,
           sizes=None, by_cohort=None):
    """Units in cohorts (first treated period) and never treated (0); y = unit + time + effect(t - g) + noise."""
    rng = np.random.default_rng(seed)
    rows = []
    groups = list(cohorts) + [0]
    for g in groups:
        for u in range((sizes or {}).get(g, n_per)):
            a = rng.normal()
            for t in range(1, periods + 1):
                y = a + 0.3 * t + rng.normal(scale=noise)
                if trend is not None and g == trend[0]:
                    y += trend[1] * t  # this cohort drifts apart before (and after) treatment
                if g and t >= g:
                    y += by_cohort[g] if by_cohort else effect(t - g)
                rows.append((f"{g}-{u}", t, g, y))
    unit = np.array([r[0] for r in rows])
    time = np.array([r[1] for r in rows])
    cohort = np.array([r[2] for r in rows])
    y = np.array([r[3] for r in rows])
    return y, unit, time, cohort


def test_with_a_constant_effect_twfe_and_group_time_agree():
    y, unit, time, cohort = _panel(effect=lambda e: 2.0)
    d = ((cohort > 0) & (time >= cohort)).astype(float)
    assert twfe(y, unit, time, d)["coef"] == pytest.approx(2.0, abs=0.1)
    cells = att_gt(y, unit, time, cohort)
    assert aggregate(cells, "simple")["att"] == pytest.approx(2.0, abs=0.1)


def test_with_effects_that_grow_twfe_goes_wrong_and_group_time_does_not():
    # The effect grows by 1 each period after treatment. Already-treated units serve as controls in TWFE, and
    # their growing effect is subtracted: the TWFE coefficient falls far below every true effect.
    y, unit, time, cohort = _panel(effect=lambda e: 1.0 + e, noise=0.2)
    d = ((cohort > 0) & (time >= cohort)).astype(float)
    cells = att_gt(y, unit, time, cohort)
    true = np.mean([1.0 + (t - g) for g in (4, 6, 8) for t in range(g, 11)])
    assert aggregate(cells, "simple")["att"] == pytest.approx(true, abs=0.1)
    assert twfe(y, unit, time, d)["coef"] < 0.6 * true
    ev = aggregate(cells, "event")
    assert ev[0]["att"] == pytest.approx(1.0, abs=0.15) and ev[4]["att"] == pytest.approx(5.0, abs=0.2)


def test_pre_period_cells_show_a_trend_that_parallel_trends_would_forbid():
    y, unit, time, cohort = _panel(trend=(8, 0.4), effect=lambda e: 0.0, noise=0.2)
    ev = aggregate(att_gt(y, unit, time, cohort), "event")
    leads = [ev[e]["att"] for e in ev if e < 0]
    assert np.mean(leads) > 0.25  # the cohort pulls away period by period before it is treated


def test_cells_use_the_period_before_treatment_after_and_the_previous_period_before():
    y, unit, time, cohort = _panel(seed=3)
    cells = {(c["g"], c["t"]): c for c in att_gt(y, unit, time, cohort)}
    assert cells[(6, 8)]["base"] == 5
    assert cells[(6, 3)]["base"] == 2


def test_cluster_bootstrap_gives_a_standard_error_near_the_spread():
    sims = []
    for seed in range(40):
        y, unit, time, cohort = _panel(seed=100 + seed, n_per=30, effect=lambda e: 1.0)
        sims.append(aggregate(att_gt(y, unit, time, cohort), "simple")["att"])
    y, unit, time, cohort = _panel(seed=99, n_per=30, effect=lambda e: 1.0)
    se = aggregate(att_gt(y, unit, time, cohort, boot=199, seed=0), "simple")["se"]
    assert 0.6 * np.std(sims) < se < 1.6 * np.std(sims)


def test_unbalanced_panels_and_missing_controls_stop():
    y, unit, time, cohort = _panel()
    with pytest.raises(SystemExit, match="balanced"):
        att_gt(y[1:], unit[1:], time[1:], cohort[1:])
    keep = cohort > 0
    with pytest.raises(SystemExit, match="never"):
        att_gt(y[keep], unit[keep], time[keep], cohort[keep])


def test_the_simple_aggregate_weights_cells_by_cohort_size():
    # Cohort 4: 60 units, effect 1, 7 post periods. Cohort 8: 20 units, effect 3, 3 post periods.
    # (60 x 7 x 1 + 20 x 3 x 3) / (60 x 7 + 20 x 3) = 1.25; an unweighted mean of the cells would give 1.6.
    y, unit, time, cohort = _panel(cohorts=(4, 8), sizes={4: 60, 8: 20, 0: 60}, by_cohort={4: 1.0, 8: 3.0}, noise=0.1)
    assert aggregate(att_gt(y, unit, time, cohort), "simple")["att"] == pytest.approx(1.25, abs=0.05)
