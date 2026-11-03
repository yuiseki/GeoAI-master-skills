# env -u PYTHONPATH uvx --from pytest --with 'duckdb>=1.5.5' --with numpy pytest -p no:cacheprovider projects/_traffic_accident/tokyo23-ward-comparison/scripts/test_analyze.py
import numpy as np
import pytest

from analyze import KNOWN, standardised, top_share, trend_class


def test_trend_class_follows_the_interval_rule_of_the_ward_projects():
    # Taito 2019 715 and 2025 667: the Poisson intervals overlap, so neither more nor fewer.
    assert trend_class(715, 667) == "区別できない"
    # A rise to 161.5% (Shinjuku's index in 2025) from 800 a year: the intervals are far apart.
    assert trend_class(800, 1292) == "増えた"
    assert trend_class(1292, 800) == "減った"


def test_standardised_differences_use_the_23_wards_mean_and_sd():
    z = standardised([1.0, 2.0, 3.0])
    assert z == pytest.approx([-1.0, 0.0, 1.0])
    # A feature equal in every ward has no direction: zeros, not a division by zero.
    assert standardised([0.4, 0.4]) == [0.0, 0.0]


def test_top_share_counts_the_largest_units_up_to_the_fraction_rounded_up():
    # 10 units, the top 10% is 1 unit: 50 of 100 accidents.
    assert top_share([50, 10, 10, 5, 5, 5, 5, 5, 5, 0], 0.1) == pytest.approx(0.5)
    # 11 units: 10% is 1.1, rounded up to 2 units.
    assert top_share([30, 20] + [5] * 9, 0.1) == pytest.approx(50 / 95)
    assert np.isnan(top_share([0, 0], 0.1))


def test_known_division_covers_the_23_wards_once():
    codes = [c for group in KNOWN.values() for c in group]
    assert sorted(codes) == [f"{i}" for i in range(101, 124)]


def test_cluster_rule_needs_both_stabilities_and_agreement():
    from clusters import passes, stabilities
    text = ("k=2                    clusters 2, noise 0, silhouette 0.440, stability ARI 1.000 (sd 0.000), ARI vs x 0.3\n"
            "    sizes: 0:5, 1:18\n"
            "k=3                    clusters 3, noise 0, silhouette 0.210, stability ARI 0.559 (sd 0.204)\n")
    assert stabilities(text) == {2: 1.0, 3: 0.559}
    assert passes(1.0, 0.995, 1.0)
    assert not passes(0.559, 0.9, 1.0) and not passes(0.9, 0.9, 0.5)


def test_principal_components_recover_a_dominant_direction_with_a_fixed_sign():
    from clusters import principal_components
    rng = np.random.default_rng(1)
    t = rng.normal(size=200)
    z = np.column_stack([t, -t, rng.normal(scale=0.1, size=200)])
    explained, loadings, scores = principal_components(z)
    assert explained[0] > 0.9
    assert abs(loadings[0][0]) == pytest.approx(abs(loadings[0][1]), abs=0.05)
    assert loadings[0][np.argmax(np.abs(loadings[0]))] > 0
    assert scores.shape == (200, 2)


def test_notable_features_are_split_by_sign_and_sorted_by_size():
    from summarize import notable
    z = {"a": "1.5", "b": "-2.0", "c": "0.4", "d": "2.2", "e": "-1.0"}
    assert notable(z, ["a", "b", "c", "d", "e"]) == (["d", "a"], ["b", "e"])
