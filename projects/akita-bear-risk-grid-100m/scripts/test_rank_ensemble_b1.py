"""Known-answer and gate tests for the fixed B1 percentile-rank ensemble."""

import numpy as np
import pytest

import rank_ensemble_b1 as experiment


def test_percentile_ranks_average_ties_and_are_scale_invariant():
    score = np.array([10.0, 10.0, 20.0, 30.0])
    expected = np.array([0.25, 0.25, 0.625, 0.875])
    np.testing.assert_allclose(experiment.percentile_rank(score), expected)
    np.testing.assert_allclose(experiment.percentile_rank(100 * score + 7), expected)
    with pytest.raises(ValueError, match="finite"):
        experiment.percentile_rank(np.array([1.0, np.nan]))


def test_exact_three_rank_mixtures_not_raw_score_mixtures():
    classifier = np.array([10.0, 20.0, 30.0, 40.0])
    poisson = np.array([4000.0, 3000.0, 2000.0, 1000.0])
    scores = experiment.ensemble_scores(classifier, poisson)
    assert list(scores) == ["E25", "E50", "E75"]
    np.testing.assert_allclose(scores["E25"], [.3125, .4375, .5625, .6875])
    np.testing.assert_allclose(scores["E50"], [.5, .5, .5, .5])
    np.testing.assert_allclose(scores["E75"], [.6875, .5625, .4375, .3125])


def test_reconstruction_fits_only_once_and_blocks_on_wrong_prior_metrics():
    calls = []

    class FakeModel:
        def predict(self, X):
            return np.array([0.1, 0.2, 0.3, 0.4])

    def fake_fit(X, counts):
        calls.append((X.copy(), counts.copy()))
        return FakeModel()

    X = np.arange(4, dtype=float).reshape(-1, 1)
    counts = np.array([0, 1, 0, 2])
    y = np.array([False, True, False, True])
    reference = experiment.evaluate_one(np.array([0.1, 0.2, 0.3, 0.4]), y, counts)
    score, measured = experiment.reconstruct_count_scores(fake_fit, X, counts, X, y, counts,
                                                           reference)
    assert len(calls) == 1
    np.testing.assert_array_equal(score, [0.1, 0.2, 0.3, 0.4])
    assert measured == reference
    wrong = dict(reference, **{"capture@5%": 0.9})
    with pytest.raises(ValueError, match="reproduce"):
        experiment.reconstruct_count_scores(fake_fit, X, counts, X, y, counts, wrong)


def test_best_of_three_uses_capture5_and_fixed_tie_order():
    rows = [{"setting": "E25", "capture@5%": 0.4},
            {"setting": "E50", "capture@5%": 0.5},
            {"setting": "E75", "capture@5%": 0.5}]
    assert experiment.choose_best(rows) == "E50"
    assert experiment.choose_best([dict(r, **{"capture@5%": 0.5}) for r in rows]) == "E25"


def test_saved_float32_baseline_only_allows_tiny_auc_ap_roundoff():
    reference = {key: 0.5 for key in experiment.prior.METRICS}
    measured = dict(reference, auc=0.5 - 2e-9, ap=0.5 - 2e-9)
    experiment.require_reproduction(measured, reference, "saved B_env", saved_float32=True)
    with pytest.raises(ValueError, match="reproduce"):
        experiment.require_reproduction(measured, reference, "count_poisson")
    wrong_capture = dict(reference, **{"capture@5%": 0.5 - 2e-9})
    with pytest.raises(ValueError, match="reproduce"):
        experiment.require_reproduction(wrong_capture, reference, "saved B_env",
                                        saved_float32=True)
