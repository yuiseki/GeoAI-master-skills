"""Known-answer tests for the Ministry mesh consistency check."""

import numpy as np
import pytest

import interface_biodic as ib


def test_mesh5_code_names_the_5km_cell_by_its_centre_3rd_order_code():
    # lat 39.7 -> 1st 59 (59.55), 2nd row 4 (0.55*8 = 4.4), lower half -> 2
    # lon 140.1 -> 1st 40, 2nd column 0 (0.1*8 = 0.8), east half -> 7
    assert ib.mesh5_code(np.array([140.1]), np.array([39.7])).tolist() == ["59404027"]
    # lat 39.7167 -> 0.575*8 = 4.6, upper half -> 7; lon 140.124 -> 0.992, east half -> 7
    assert ib.mesh5_code(np.array([140.124]), np.array([39.7167])).tolist() == ["59404077"]


def test_record_level_counts_the_two_surveys():
    assert ib.record_level(np.array(["0", "1", "0", "1"]), np.array(["0", "0", "1", "1"])).tolist() == [0, 1, 1, 2]


def test_spearman_diff_is_positive_when_the_first_proxy_follows_the_level():
    rng = np.random.default_rng(0)
    level = np.repeat([0, 1, 2], 40)
    a = level + rng.normal(0, 0.3, len(level))
    b = rng.normal(0, 1, len(level))
    blocks = np.arange(len(level)) // 2
    d, lo, hi = ib.spearman_diff(level, a, b, blocks, B=200, seed=0)
    assert d > 0.5 and lo > 0
    d2, lo2, hi2 = ib.spearman_diff(level, b, a, blocks, B=200, seed=0)
    assert d2 == pytest.approx(-d) and hi2 < 0


def test_reading_follows_the_preregistered_rule():
    assert ib.reading(0.01, 0.05).startswith("M_B")
    assert ib.reading(-0.05, -0.01).startswith("the Ministry")
    assert ib.reading(-0.01, 0.02).startswith("no difference")
