"""uvx --with numpy --with pytest pytest test_design_checks.py

Every population is built from exact counts with no noise, so each number is worked out by hand.
"""

import numpy as np
import pytest

from design_checks import (bias_grid, diff_in_means, distance_to_treated, neighbour_share, ols, overlap,
                           standardize)


def cells(*spec):
    """(count, t, l, y) -> arrays t, l, y with count copies of each row."""
    t, l, y = [], [], []
    for n, ti, li, yi in spec:
        t += [ti] * n
        l += [li] * n
        y += [yi] * n
    return np.array(t), np.array(l), np.array(y, float)


# L = 1 makes treatment likely (80 of 100) and adds 2 to the outcome. Treatment does nothing.
T, L, Y = cells((80, 0, 0, 0), (20, 1, 0, 0), (20, 0, 1, 2), (80, 1, 1, 2))


def test_an_unadjusted_confounder_makes_an_effect_where_there_is_none():
    # treated: 80% have L = 1 -> mean 1.6; untreated: 20% -> 0.4
    assert diff_in_means(Y, T) == pytest.approx(1.2)


def test_comparing_within_levels_of_the_confounder_gives_zero():
    assert standardize(Y, T, L)["effect"] == pytest.approx(0)


def test_ate_and_att_differ_when_the_effect_differs_by_stratum():
    # the effect is 1 where L = 0 and 3 where L = 1; the treated are mostly L = 1
    y = 2 * L + np.where(T == 1, np.where(L == 1, 3, 1), 0)
    assert standardize(y, T, L, target="ate")["effect"] == pytest.approx(2)  # 100 and 100 rows
    assert standardize(y, T, L, target="att")["effect"] == pytest.approx(2.6)  # (20 x 1 + 80 x 3) / 100
    assert diff_in_means(y, T) == pytest.approx(3.8)  # 4.2 - 0.4


def test_adjusting_a_mediator_removes_the_total_effect():
    # T moves M (80% vs 20%), and M is the whole outcome: total effect 0.6, direct effect 0
    t, m, y = cells((80, 0, 0, 0), (20, 0, 1, 1), (20, 1, 0, 0), (80, 1, 1, 1))
    assert diff_in_means(y, t) == pytest.approx(0.6)
    assert standardize(y, t, m)["effect"] == pytest.approx(0)


def test_adjusting_a_collider_makes_an_effect_and_fits_better():
    # T and Y independent, 25 rows of each pair; C = T + Y is caused by both
    t, yy, _ = cells((25, 0, 0, 0), (25, 0, 1, 0), (25, 1, 0, 0), (25, 1, 1, 0))
    y = yy.astype(float)
    c = t + y
    assert diff_in_means(y, t) == pytest.approx(0)
    b, r2 = ols(y, np.c_[t, c])
    assert b[1] == pytest.approx(-1)  # y = c - t exactly
    assert r2 == pytest.approx(1)  # a perfect fit with the wrong answer
    assert ols(y, t[:, None])[1] == pytest.approx(0)
    # a descendant of the collider (D = 1 when C >= 1): cell means give 0, 1 and 0.5 -> slope -0.5
    d = (c >= 1).astype(float)
    assert ols(y, np.c_[t, d])[0][1] == pytest.approx(-0.5)


def test_no_treated_rows_in_a_stratum_means_no_ate_only_an_extrapolation():
    # urban (half the units) has treated and untreated rows; rural has none treated.
    # The true effect is 1 in urban and 3 in rural: true ATE 2, but rural's 3 is never observed.
    t, rural, _ = cells((50, 0, 0, 0), (50, 1, 0, 0), (100, 0, 1, 0))
    y = 5 * rural + t * 1.0
    r = standardize(y, t, rural, target="ate")
    assert r["effect"] is None and r["unsupported"] == [1] and r["unsupported_share"] == pytest.approx(0.5)
    assert standardize(y, t, rural, target="att")["effect"] == pytest.approx(1)  # all treated are urban
    assert standardize(y, t, rural, target="ate", supported_only=True)["effect"] == pytest.approx(1)
    # a regression gives an ATE anyway: its rural effect is the urban one carried over by the model
    assert ols(y, np.c_[t, rural])[0][1] == pytest.approx(1)
    table = overlap(t, rural)
    assert table == [{"stratum": 0, "treated": 50, "untreated": 50, "supported": True},
                     {"stratum": 1, "treated": 0, "untreated": 100, "supported": False}]


# A line of 20 units, each the neighbour of the next. 5..9 is a treated block, 15 a lone treated unit.
LINE = [[j for j in (i - 1, i + 1) if 0 <= j < 20] for i in range(20)]
TLINE = np.zeros(20, int)
TLINE[[5, 6, 7, 8, 9, 15]] = 1


def test_treated_neighbour_share_and_distance_to_treatment():
    s = neighbour_share(TLINE, LINE)
    assert s[[4, 5, 6, 9, 10, 15, 0]].tolist() == [0.5, 0.5, 1, 0.5, 0.5, 0, 0]
    xy = np.c_[np.arange(20) * 100.0, np.zeros(20)]
    dist = distance_to_treated(TLINE, xy)
    assert dist[[0, 4, 5, 12, 15]].tolist() == [500, 100, 100, 300, 600]  # another treated unit, never itself


def test_own_treatment_alone_mistakes_spillover_for_an_effect():
    # treatment does nothing to its own unit; each unit gains its share of treated neighbours
    y = neighbour_share(TLINE, LINE)
    # treated mean (0.5 + 1 + 1 + 1 + 0.5 + 0) / 6 = 2/3; untreated 4 x 0.5 / 14 = 1/7
    assert diff_in_means(y, TLINE) == pytest.approx(2 / 3 - 1 / 7)
    b, _ = ols(y, np.c_[TLINE, neighbour_share(TLINE, LINE)])
    assert b[1:] == pytest.approx([0, 1], abs=1e-12)


def test_a_coarse_region_leaves_most_of_a_spatial_confounder():
    # 10 columns of 12 units; the outcome is the column x (a smooth gradient nobody measured),
    # and x + 1 units of column x are treated
    x = np.repeat(np.arange(10), 12)
    t = np.concatenate([[1] * (k + 1) + [0] * (11 - k) for k in range(10)])
    y = x.astype(float)
    assert diff_in_means(y, t) == pytest.approx(6 - 210 / 65)  # 2.769
    # west (0..4): 40/15 - 80/45 = 8/9; east (5..9): 29/4 - 13/2 = 3/4; equal halves
    assert standardize(y, t, x >= 5)["effect"] == pytest.approx(59 / 72)
    assert standardize(y, t, x)["effect"] == pytest.approx(0)


def test_a_hidden_confounder_of_a_given_strength_explains_an_estimate():
    r = bias_grid(0.6, gammas=[0.5, 1.0], deltas=[0.2, 0.6])
    assert np.ravel(r["adjusted"]) == pytest.approx([0.5, 0.3, 0.4, 0.0])
    assert r["explains"] == [[False, False], [False, True]]


def test_the_bias_formula_holds_for_a_binary_hidden_confounder():
    # U is 1 for 70% of the treated and 20% of the untreated (delta 0.5) and adds 1.2 (gamma)
    t, u, _ = cells((80, 0, 0, 0), (20, 0, 1, 0), (30, 1, 0, 0), (70, 1, 1, 0))
    y = 1.2 * u
    est = diff_in_means(y, t)
    assert est == pytest.approx(0.6)
    assert bias_grid(est, [1.2], [0.5])["adjusted"][0][0] == pytest.approx(0, abs=1e-12)


def test_a_negative_control_outcome_shows_confounding_that_l_did_not_remove():
    # L is adjusted; U is not. N cannot be moved by T but shares U with the treatment.
    t, l, u = cells((40, 0, 0, 0), (10, 0, 0, 1), (10, 1, 0, 0), (40, 1, 0, 1),
                    (40, 0, 1, 0), (10, 0, 1, 1), (10, 1, 1, 0), (40, 1, 1, 1))
    n = u.copy()
    assert standardize(n, t, l)["effect"] == pytest.approx(0.6)  # 0.8 - 0.2 in both strata, not 0
