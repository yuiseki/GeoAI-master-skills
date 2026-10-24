"""Regression tests for the shelter-demand choropleth input."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("reproduce_map", Path(__file__).with_name("reproduce_map.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validate_towns_checks_report_population_and_density():
    rows = [("a", 100, 10, 10), ("b", 200, 20, 10)]
    assert MODULE.validate_towns(rows, expected_population=300) == 2
    with pytest.raises(ValueError, match="population"):
        MODULE.validate_towns(rows, expected_population=301)
    with pytest.raises(ValueError, match="density"):
        MODULE.validate_towns([("a", 100, 10, 11)], expected_population=100)


def test_validate_towns_rejects_duplicate_ids_and_zero_area():
    with pytest.raises(ValueError, match="duplicate"):
        MODULE.validate_towns([("a", 10, 1, 10), ("a", 10, 1, 10)], expected_population=20)
    with pytest.raises(ValueError, match="area"):
        MODULE.validate_towns([("a", 10, 0, 10)], expected_population=10)
