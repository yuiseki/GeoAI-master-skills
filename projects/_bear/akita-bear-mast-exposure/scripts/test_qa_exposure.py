"""Tests for the exposure QA helpers."""

import numpy as np

import qa_exposure as qa


def test_mesh_cell_index_uses_the_20m_cell_centre():
    ix, iy = qa.mesh_index(np.array([-97400 + 80, -97400 + 90]), np.array([-125100, -125100]), -97400, -125100)
    assert list(ix) == [0, 1] and list(iy) == [0, 0]


def test_share_of_area_in_cells_over_a_threshold():
    area = np.array([10.0, 30.0, 60.0])
    other = np.array([0.6, 0.4, 0.5])
    assert np.isclose(qa.share_in(area, other, 0.5), 70 / 100)


def test_describe_counts_zeros_and_ignores_nan():
    d = qa.describe(np.array([0, 0, 0.5, 1.0, np.nan]))
    assert d["n"] == 4 and d["n_nan"] == 1 and d["zero_share"] == 0.5 and d["max"] == 1.0
