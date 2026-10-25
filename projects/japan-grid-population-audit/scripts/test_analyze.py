"""uv run --no-project --with pytest --with numpy --with pyproj python3 -m pytest -q projects/japan-grid-population-audit/scripts/test_analyze.py"""

import math

import numpy as np
import pytest
from analyze import (
    Tile,
    aggregate_census_rows,
    aggregate_landcover,
    assemble_grid,
    estimate_mesh,
    mesh_bounds,
    overlap_fraction,
    ranked_overlap,
)


def test_mesh_code_decodes_tokyo_station_example():
    west, south, east, north = mesh_bounds("53394611")
    assert (west, south) == pytest.approx((139.7625, 35.675))
    assert east - west == pytest.approx(1 / 80)
    assert north - south == pytest.approx(1 / 120)


def test_invalid_mesh_code_stops():
    with pytest.raises(ValueError):
        mesh_bounds("5339461x")


def test_exact_area_fraction_partitions_source_cell():
    source = (139.0, 35.0, 139.02, 35.01)
    left = (139.0, 35.0, 139.01, 35.01)
    right = (139.01, 35.0, 139.02, 35.01)
    assert overlap_fraction(source, left) == pytest.approx(0.5, abs=1e-10)
    assert overlap_fraction(source, left) + overlap_fraction(
        source, right
    ) == pytest.approx(1, abs=1e-10)
    assert overlap_fraction(source, (140.0, 35.0, 140.01, 35.01)) == 0


def test_area_transfer_preserves_population_but_centroid_is_discontinuous():
    tile = Tile("A", 139.0, 35.01, 0.02, 0.01, np.array([[100.0]]))
    left = estimate_mesh((139.0, 35.0, 139.01, 35.01), (tile,))
    right = estimate_mesh((139.01, 35.0, 139.02, 35.01), (tile,))
    assert left.area_population == pytest.approx(50)
    assert right.area_population == pytest.approx(50)
    assert left.area_population + right.area_population == pytest.approx(100)
    assert left.center_population + right.center_population == pytest.approx(100)
    assert left.coverage == pytest.approx(1)
    assert right.coverage == pytest.approx(1)


def test_adjacent_tiles_leave_no_gap_or_double_count():
    west_tile = Tile("W", 139.0, 35.01, 0.01, 0.01, np.array([[30.0]]))
    east_tile = Tile("E", 139.01, 35.01, 0.01, 0.01, np.array([[70.0]]))
    result = estimate_mesh((139.0, 35.0, 139.02, 35.01), (west_tile, east_tile))
    assert result.area_population == pytest.approx(100)
    assert result.center_population == pytest.approx(100)
    assert result.coverage == pytest.approx(1)
    assert result.overlap_cells == 2


def test_census_prefecture_duplicate_is_added_not_dropped():
    values, audit = aggregate_census_rows(
        [
            ("13", "53394611", "1157"),
            ("14", "53394611", "43"),
            ("13", "53394612", "0"),
        ]
    )
    assert values == {"53394611": 1200, "53394612": 0}
    assert audit["input_rows"] == 3
    assert audit["duplicate_mesh_codes"] == 1
    assert audit["population_total"] == 1200


def test_census_suppression_is_not_zero():
    with pytest.raises(ValueError):
        aggregate_census_rows([("13", "53394611", "*")])


def test_rank_overlap_tie_breaks_by_code():
    census = {"a": 10, "b": 10, "c": 1}
    estimate = {"a": 10, "b": 1, "c": 10}
    result = ranked_overlap(census, estimate, 1)
    assert result["census_top"] == ["a"]
    assert result["estimate_top"] == ["a"]
    assert result["overlap"] == 1
    assert math.isclose(result["recall"], 1.0)


def test_assemble_grid_reorders_rows_and_checks_completeness():
    grid = assemble_grid(
        np.array([1, 0, 1, 0]),
        np.array([1, 0, 0, 1]),
        np.array([4.0, 1.0, 3.0, 2.0]),
        (2, 2),
    )
    assert grid.tolist() == [[1, 2], [3, 4]]
    with pytest.raises(ValueError, match="duplicate"):
        assemble_grid(np.array([0, 0]), np.array([0, 0]), np.array([1.0, 2.0]), (1, 2))
    with pytest.raises(ValueError, match="missing"):
        assemble_grid(np.array([0]), np.array([0]), np.array([1.0]), (1, 2))


def test_landcover_counts_are_area_weighted_not_class_codes_averaged():
    tile = Tile("cover", 139.0, 35.01, 0.01, 0.01, np.zeros((1, 2)))
    counts = np.array([[[100, 0], [0, 100]]], dtype=float)
    result = aggregate_landcover((139.0, 35.0, 139.02, 35.01), tile, counts)
    assert result["coverage"] == pytest.approx(1)
    assert result["shares"] == pytest.approx([0.5, 0.5])
    assert result["mixedness"] == pytest.approx(0.5)
    with pytest.raises(ValueError, match="negative"):
        aggregate_landcover((139.0, 35.0, 139.02, 35.01), tile, -counts)
