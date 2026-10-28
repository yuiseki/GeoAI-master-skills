"""Tests for the alignment of the saved B_env surfaces, the labels, the exposure and the mast values."""

import numpy as np

import data


def test_mast_scarcity_is_five_minus_the_index():
    rows = [("2023", "秋田県", "fruiting", "0.1"), ("2023", "秋田県", "flowering", "0.3"), ("2023", "青森県", "fruiting", "1.0")]
    s = data.mast_scarcity(rows, "fruiting")
    assert s == {2023: 4.9}
    assert data.mast_scarcity(rows, "flowering") == {2023: 4.7}


def test_prefecture_vector_is_row_major_south_first():
    muni = np.array([[0, -1], [1, 2]])  # row 0 = south
    a = np.array([[10, 11], [12, 13]])
    assert list(data.vec(a, muni)) == [10, 12, 13]


def test_exposure_nan_becomes_zero():
    muni = np.zeros((1, 2), dtype=int)
    e = {"beech_oak_fraction_500": np.array([[np.nan, 0.5]], dtype=np.float32)}
    v, n = data.exposure_vec(e, "beech_oak_fraction_500", muni)
    assert list(v) == [0.0, 0.5] and n == 1
