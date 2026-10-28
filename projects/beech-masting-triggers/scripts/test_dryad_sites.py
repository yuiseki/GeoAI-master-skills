"""Known-answer tests for rebuilding the prefecture index from Dryad site ranks."""

import pytest

import dryad_sites as ds


def test_weights_follow_the_forest_office_index():
    assert ds.rebuilt_index([3, 2, 1, 0]) == pytest.approx((5 + 3 + 1 + 0) / 4)
    assert ds.rebuilt_index([3, 3]) == 5


def test_minus_one_and_missing_are_left_out():
    assert ds.rebuilt_index([3, -1, 0]) == pytest.approx(2.5)
    assert ds.rebuilt_index([-1, -1]) is None
    assert ds.rebuilt_index([]) is None
