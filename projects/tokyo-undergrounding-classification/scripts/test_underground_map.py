"""Regression tests for the undergrounding choropleth input."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("reproduce_map", Path(__file__).with_name("reproduce_map.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_aggregate_cells_preserves_low_sample_cells_as_nodata():
    rows = MODULE.aggregate_cells([12] * 30 + [13] * 29, [1] * 12 + [0] * 18 + [1] * 29)
    assert rows == [(12, 30, pytest.approx(0.4)), (13, 29, None)]


def test_aggregate_cells_rejects_mismatched_rows_and_nonbinary_labels():
    with pytest.raises(ValueError, match="row count"):
        MODULE.aggregate_cells([1], [])
    with pytest.raises(ValueError, match="binary"):
        MODULE.aggregate_cells([1], [2])
