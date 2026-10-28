import numpy as np

import features as ft


def test_box_sum_counts_the_square_window_and_zero_outside():
    a = np.zeros((7, 7))
    a[3, 3] = 1.0
    s = ft.box_sum(a, 1)
    assert s[3, 3] == 1 and s[2, 2] == 1 and s[1, 1] == 0 and np.isclose(s.sum(), 9)
    b = np.ones((3, 3))
    assert ft.box_sum(b, 1)[0, 0] == 4  # the corner sees 4 cells; outside counts as 0


def test_box_mean_ignores_nan():
    a = np.array([[1.0, np.nan], [3.0, 5.0]])
    m = ft.box_mean(a, 1)
    assert np.isclose(m[0, 0], 3.0)
    assert np.isnan(ft.box_mean(np.full((2, 2), np.nan), 1)).all()


def test_history_uses_only_years_before_the_target():
    rng = np.random.default_rng(0)
    counts = {y: rng.poisson(0.2, size=(30, 30)).astype(float) for y in (2022, 2023, 2024, 2025)}
    h1 = ft.history_features(counts, 2024)
    counts2 = dict(counts)
    counts2[2024] = counts[2024] * 0 + 50  # the target year and after are changed
    counts2[2025] = counts[2025] * 0 + 99
    h2 = ft.history_features(counts2, 2024)
    for k in h1:
        np.testing.assert_array_equal(np.nan_to_num(h1[k], nan=-1), np.nan_to_num(h2[k], nan=-1), err_msg=k)


def test_history_is_a_share_of_the_year_total_so_a_tenfold_year_looks_the_same():
    a = np.zeros((10, 10))
    a[5, 5] = 2
    a[1, 1] = 1
    h_small = ft.history_features({2022: a, 2023: a}, 2023)
    h_big = ft.history_features({2022: a * 10, 2023: a}, 2023)
    np.testing.assert_allclose(h_small["h_prev_r1000"], h_big["h_prev_r1000"])


def test_distance_to_the_nearest_past_report():
    a = np.zeros((5, 5))
    a[0, 0] = 1
    h = ft.history_features({2022: a, 2023: np.zeros((5, 5))}, 2023)
    assert h["h_dist"][0, 0] == 0 and h["h_dist"][0, 3] == 300


def test_history_needs_at_least_one_past_year():
    try:
        ft.history_features({2023: np.zeros((3, 3))}, 2023)
        raise AssertionError("should stop")
    except ValueError:
        pass
