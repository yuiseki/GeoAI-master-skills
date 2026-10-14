"""uvx --with numpy --with scipy --with pytest pytest test_privacy_check.py

Small layouts whose answers are counted by hand. Coordinates are metres.
"""

import numpy as np
import pytest

from privacy_check import average_releases, cell_counts, donut_mask, home_location, nearest_candidate_hits, \
    candidates_within


def test_cell_counts_suppress_cells_below_the_minimum_and_report_what_was_hidden():
    # cells of 100 m: (0,0) holds 3 points, (1,0) holds 1, (0,1) holds 5
    xy = [(10, 10), (20, 20), (30, 30), (150, 50), (50, 150), (60, 160), (70, 170), (80, 180), (90, 190)]
    r = cell_counts(xy, cell=100, min_count=3)
    assert r["counts"] == {(0, 0): 3, (1, 0): None, (0, 1): 5}  # None: suppressed, not 0
    assert r["suppressed_cells"] == 1 and r["suppressed_points"] == 1
    assert r["unique_cells"] == 1  # a cell with exactly one point singles that point out


def test_cell_counts_without_a_minimum_publish_every_count():
    r = cell_counts([(10, 10), (150, 50)], cell=100, min_count=1)
    assert r["counts"] == {(0, 0): 1, (1, 0): 1} and r["suppressed_cells"] == 0


def test_donut_mask_moves_every_point_between_the_two_radii():
    xy = np.zeros((2000, 2))
    m = donut_mask(xy, r_min=50, r_max=100, seed=0)
    d = np.hypot(*m.T)
    assert d.min() >= 50 and d.max() <= 100
    # uniform in area: the share inside radius 75 is (75^2 - 50^2) / (100^2 - 50^2) = 0.4167
    assert np.mean(d < 75) == pytest.approx(0.4167, abs=0.03)


def test_nearest_candidate_attack_finds_the_true_house_when_houses_are_sparse():
    houses = np.array([(0, 0), (1000, 0), (0, 1000)])
    masked = np.array([(60, 30), (950, 80), (40, 900)])
    assert nearest_candidate_hits(masked, houses, true_index=[0, 1, 2]) == [True, True, True]
    dense = np.array([(0, 0), (40, 20), (1000, 0), (0, 1000)])
    assert nearest_candidate_hits(masked, dense, true_index=[0, 2, 3]) == [False, True, True]  # (40,20) is nearer


def test_candidates_within_counts_the_houses_a_masked_point_could_have_come_from():
    houses = np.array([(0, 0), (30, 0), (0, 30), (500, 500)])
    assert list(candidates_within(np.array([(10, 10), (480, 480)]), houses, radius=50)) == [3, 1]


def test_averaging_independent_releases_of_the_same_point_undoes_the_jitter():
    xy = np.zeros((1, 2))
    one = np.hypot(*donut_mask(xy, 50, 100, seed=1)[0])
    avg = average_releases(xy, 50, 100, releases=50, seed=1)
    assert one >= 50
    assert np.hypot(*avg[0]) < 25  # the mean of 50 jittered copies sits near the true point


def test_home_is_the_most_frequent_night_cell_of_a_trace():
    # night (22-6 h) points cluster in cell (3,4); day points in cell (10,10)
    xy = [(350, 450)] * 4 + [(1050, 1050)] * 6 + [(360, 460)]
    hours = [23, 1, 2, 5, 10, 11, 14, 15, 16, 17, 3]
    h = home_location(xy, hours, cell=100)
    assert h["cell"] == (3, 4) and h["night_points"] == 5
    assert h["xy"] == pytest.approx((350, 450))  # the centre of the cell
