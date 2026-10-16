"""uvx --with numpy --with pytest pytest test_match.py"""

import numpy as np
import pytest

from match import att_matching, nearest_controls, smd


def test_known_answer_with_one_nearest_control_each():
    # Treated at x = 0 (y 10) and 2 (y 14); controls at 0.1 (y 7), 1.9 (y 8), 5 (y 30).
    x = np.array([[0.0], [2.0], [0.1], [1.9], [5.0]])
    t = np.array([1, 1, 0, 0, 0])
    y = np.array([10.0, 14, 7, 8, 30])
    r = att_matching(y, t, x, k=1)
    assert r["att"] == pytest.approx(((10 - 7) + (14 - 8)) / 2)
    assert r["matched_treated"] == 2 and r["controls_used"] == 2


def test_ties_are_all_kept_and_averaged():
    x = np.array([[0.0], [-1.0], [1.0], [3.0]])
    t = np.array([1, 0, 0, 0])
    y = np.array([10.0, 4, 6, 100])
    sets = nearest_controls(x[t == 1], x[t == 0], np.ones(1), k=1)
    assert sorted(sets[0].tolist()) == [0, 1]  # both at distance 1
    assert att_matching(y, t, x, k=1)["att"] == pytest.approx(10 - 5)


def test_a_caliper_drops_treated_without_a_close_control_and_says_so():
    x = np.array([[0.0], [10.0], [0.2], [0.4]])
    t = np.array([1, 1, 0, 0])
    y = np.array([5.0, 50, 1, 2])
    r = att_matching(y, t, x, k=1, caliper=1.0)
    assert r["matched_treated"] == 1 and r["dropped_treated"] == 1
    assert r["att"] == pytest.approx(5 - 1)


def _world(seed, n=600, effect=2.0, curved=False):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 2))
    p = 1 / (1 + np.exp(-(1.2 * x[:, 0] - 0.5)))
    t = (rng.random(n) < p).astype(int)
    y = effect * t + 3 * x[:, 0] + (x[:, 1] ** 2 if curved else x[:, 1]) + rng.normal(size=n)
    return y, t, x


def test_bias_adjustment_removes_the_bias_of_imperfect_matches():
    # Few controls at high x: matches fall short, and y rises steeply with x.
    raw, adj = [], []
    for seed in range(30):
        y, t, x = _world(seed)
        raw.append(att_matching(y, t, x, k=1)["att"])
        adj.append(att_matching(y, t, x, k=1, bias_adjust=True)["att"])
    assert abs(np.mean(adj) - 2) < abs(np.mean(raw) - 2)
    assert abs(np.mean(adj) - 2) < 0.1


def test_abadie_imbens_intervals_cover_about_95_percent():
    covered = 0
    for seed in range(200):
        y, t, x = _world(1000 + seed, n=500)
        r = att_matching(y, t, x, k=4, bias_adjust=True)
        covered += abs(r["att"] - 2) <= 1.96 * r["se"]
    assert 0.90 <= covered / 200 <= 0.99


def test_a_linear_adjustment_leaves_curvature_bias_that_grows_with_k():
    # y bends in x2: matched controls spread around x2, and a straight line cannot move them back.
    bias = {}
    for k in (1, 8):
        bias[k] = np.mean([att_matching(*_world(seed, curved=True), k=k, bias_adjust=True)["att"] - 2
                           for seed in range(30)])
    assert bias[8] > bias[1] > 0


def test_matching_on_the_propensity_score_uses_its_logit():
    y, t, x = _world(5)
    r = att_matching(y, t, x, k=1, on="ps")
    assert np.isfinite(r["att"]) and r["metric"] == "logit propensity"


def test_balance_after_matching_is_better_than_before():
    y, t, x = _world(6)
    r = att_matching(y, t, x, k=1)
    assert np.abs(r["smd_after"]).max() < np.abs(r["smd_before"]).max()


def test_smd_by_hand():
    xt, xc = np.array([[1.0], [3.0]]), np.array([[0.0], [2.0]])
    assert smd(xt, xc)[0] == pytest.approx(1 / np.sqrt((2 + 2) / 2))


def test_no_control_stops():
    with pytest.raises(SystemExit):
        att_matching(np.array([1.0, 2.0]), np.array([1, 1]), np.array([[0.0], [1.0]]))
