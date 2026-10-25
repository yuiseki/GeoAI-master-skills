"""uv run --no-project --with pytest --with numpy --with scipy python3 -m pytest -q projects/japan-bus-operator-concentration-replication/scripts/test_analysis.py"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from analysis import aggregate_census, classify_neighbors, mesh_center, weighted_share


def test_census_cross_prefecture_and_suppression():
    rows = [
        ("53394611", "10", "3"),
        ("53394611", "5", "2"),
        ("53394612", "7", "*"),
        ("53394612", "1", "1"),
    ]
    result = aggregate_census(rows)
    assert result["53394611"] == (15, 5)
    assert result["53394612"] == (8, None)


def test_mesh_center_known_tokyo_station():
    lon, lat = mesh_center("53394611")
    assert lon == pytest.approx(139.76875)
    assert lat == pytest.approx(35.6791666667)


def test_operator_distinct_and_boundary():
    # At latitude 35 degrees, 0.008 degrees longitude is roughly 728m.
    lon = np.array([139.0, 139.008, 139.008, 139.03])
    lat = np.array([35.0, 35.0, 35.0, 35.0])
    operators = ["A", "A", "B", "C"]
    results = classify_neighbors(np.array([139.0]), np.array([35.0]), lon, lat, operators, (500, 800, 1000))
    assert results[500].tolist() == [1]
    assert results[800].tolist() == [2]
    assert results[1000].tolist() == [2]


def test_weighted_share_excludes_missing_and_no_stop():
    counts = np.array([0, 1, 2, 1])
    ages = [100, 20, 1000, None]
    assert weighted_share(counts, ages) == pytest.approx(20 / 1020)
