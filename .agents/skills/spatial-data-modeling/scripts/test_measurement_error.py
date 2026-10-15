"""uvx --with numpy --with pytest pytest test_measurement_error.py

The four-row tables and the 2 x 2 counts are worked out by hand; the random draws check a property.
"""

import numpy as np
import pytest

from measurement_error import (calibration_from_validation, correct_prevalence, correction_grid,
                               misclassified_exposure, observed_prevalence, ols, regression_calibration,
                               reliability, reliability_from_repeats)

# every combination of a true value x in {-1, 1} and an error u in {-1, 1}: var x = var u = 1
X4 = np.array([-1, -1, 1, 1.0])
U4 = np.array([-1, 1, -1, 1.0])


def test_classical_error_in_the_predictor_halves_the_slope_when_reliability_is_one_half():
    w = X4 + U4  # observed = true + error, error independent of the true value
    y = 2 * X4
    assert ols(y, X4)["coef"][1] == pytest.approx(2)
    assert ols(y, w)["coef"][1] == pytest.approx(1)  # cov(w, y) / var(w) = 2 / 2
    assert 2 * reliability(1, 1) == pytest.approx(1)


def test_berkson_error_leaves_the_slope_alone():
    # the assigned value w is known; each unit's true value scatters around it: x = w + u
    w = X4
    x = w + U4
    assert ols(2 * x, w)["coef"][1] == pytest.approx(2)  # cov(w, 2w + 2u) / var(w)


def test_attenuation_matches_the_reliability_ratio():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 20000)
    w = x + rng.normal(0, 0.75, 20000)
    y = 2 * x + rng.normal(0, 1, 20000)
    lam = reliability(1, 0.75 ** 2)  # 1 / 1.5625 = 0.64
    assert ols(y, w)["coef"][1] == pytest.approx(2 * lam, abs=0.04)


def test_error_in_the_outcome_widens_the_se_but_does_not_move_the_slope():
    rng = np.random.default_rng(1)
    clean, noisy = [], []
    for _ in range(200):
        x = rng.normal(0, 1, 200)
        y = 2 * x + rng.normal(0, 1, 200)
        clean.append(ols(y, x))
        noisy.append(ols(y + rng.normal(0, 2, 200), x))
    assert np.mean([r["coef"][1] for r in noisy]) == pytest.approx(2, abs=0.05)
    assert np.mean([r["se"][1] for r in noisy]) > 2 * np.mean([r["se"][1] for r in clean])


def test_reliability_from_two_repeats_by_hand():
    # pairs differ by 2: within variance 2 each. Means 2, 6, 3: variance 13/3; minus 2/2 -> true 10/3
    r = reliability_from_repeats(np.array([[1, 3], [5, 7], [2, 4.0]]))
    assert r["error_var"] == pytest.approx(2)
    assert r["true_var"] == pytest.approx(10 / 3)
    assert r["lambda_single"] == pytest.approx(10 / 16)
    assert r["lambda_mean"] == pytest.approx(10 / 13)


def test_averaging_k_repeats_divides_the_error_variance_by_k():
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, 5000)
    W = x[:, None] + rng.normal(0, 1, (5000, 4))
    r = reliability_from_repeats(W)
    assert r["error_var"] == pytest.approx(1, abs=0.05)
    assert np.var(W.mean(axis=1) - x) == pytest.approx(0.25, abs=0.02)
    assert r["lambda_mean"] == pytest.approx(1 / 1.25, abs=0.02)


def _world(seed, n=5000):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    w = x + rng.normal(0, 0.75, n)
    y = 2 * x + rng.normal(0, 1, n)
    return rng, x, w, y


def test_regression_calibration_from_a_random_validation_sample_recovers_the_slope():
    rng, x, w, y = _world(3)
    v = rng.random(len(x)) < 0.1
    a, b = calibration_from_validation(x[v], w[v])
    assert b == pytest.approx(0.64, abs=0.06)  # the reliability, when the error is classical
    assert regression_calibration(y, w, a, b)["coef"][1] == pytest.approx(2, abs=0.15)
    assert ols(y, w)["coef"][1] == pytest.approx(1.28, abs=0.06)


def test_a_validation_sample_chosen_by_the_observed_value_still_works_but_not_one_chosen_by_the_truth():
    _, x, w, y = _world(4)
    by_w = w > 0.5
    by_x = x > 0.5
    assert regression_calibration(y, w, *calibration_from_validation(x[by_w], w[by_w]))["coef"][1] == \
        pytest.approx(2, abs=0.2)
    assert regression_calibration(y, w, *calibration_from_validation(x[by_x], w[by_x]))["coef"][1] > 3


def test_observed_prevalence_and_its_correction_by_hand():
    assert observed_prevalence(0.2, 0.9, 0.95) == pytest.approx(0.22)  # 0.18 true positives + 0.04 false
    assert correct_prevalence(0.22, 0.9, 0.95) == pytest.approx(0.2)
    # a rare condition with 99% specificity: the observed rate is about twice the true one
    assert observed_prevalence(0.01, 1.0, 0.99) == pytest.approx(0.0199)


def test_a_correction_outside_zero_and_one_or_with_useless_tests_stops():
    with pytest.raises(ValueError, match="sensitivity"):
        correct_prevalence(0.3, 0.5, 0.5)
    with pytest.raises(ValueError, match="outside"):
        correct_prevalence(0.03, 0.9, 0.95)  # (0.03 - 0.05) / 0.85 < 0: the assumed rates do not fit


def test_with_unknown_rates_the_correction_is_a_grid_not_a_point():
    g = correction_grid(0.22, ses=[0.8, 0.9], sps=[0.95, 0.99])
    assert g[(0.9, 0.95)] == pytest.approx(0.2)
    assert g[(0.8, 0.99)] == pytest.approx(0.21 / 0.79)
    assert correction_grid(0.03, ses=[0.9], sps=[0.95])[(0.9, 0.95)] is None


def test_non_differential_exposure_misclassification_pulls_the_risk_difference_towards_zero():
    # 500 exposed (risk 0.3) and 500 unexposed (risk 0.1); sensitivity 0.8, specificity 0.9.
    # classified exposed: 400 + 50 rows, 120 + 5 cases; classified unexposed: 100 + 450, 30 + 45
    r = misclassified_exposure(500, 500, 0.3, 0.1, se=0.8, sp=0.9)
    assert r["risk_exposed"] == pytest.approx(125 / 450)
    assert r["risk_unexposed"] == pytest.approx(75 / 550)
    assert 0 < r["rd"] < 0.2


def test_differential_misclassification_can_push_away_from_zero():
    # cases recall their exposure better (sensitivity 0.95) than non-cases (0.6)
    r = misclassified_exposure(500, 500, 0.3, 0.1, se=0.6, sp=0.9, se_cases=0.95, sp_cases=0.9)
    # exposed: cases 142.5 + 5, non-cases 210 + 45 -> 147.5 / 402.5; unexposed: 7.5 + 45, 140 + 405
    assert r["risk_exposed"] == pytest.approx(147.5 / 402.5)
    assert r["risk_unexposed"] == pytest.approx(52.5 / 597.5)
    assert r["rd"] > 0.2


def test_non_differential_outcome_misclassification_scales_the_risk_difference():
    # risk difference times (se + sp - 1): 0.31 - 0.17 = 0.7 x 0.2
    rd = observed_prevalence(0.3, 0.8, 0.9) - observed_prevalence(0.1, 0.8, 0.9)
    assert rd == pytest.approx(0.7 * 0.2)
