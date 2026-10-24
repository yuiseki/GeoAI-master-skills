"""Small known-answer checks for the accident-mesh analysis."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "accident_analysis", Path(__file__).with_name("analyze.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_mesh_code_round_trip_at_tokyo_station():
    code = MODULE.mesh_code(139.7671, 35.6812)
    assert code == "53394611"
    west, south, east, north = MODULE.mesh_bounds(code)
    assert (west, south, east, north) == pytest.approx(
        (139.7625, 35.675, 139.775, 35.6833333333)
    )
    assert west <= 139.7671 < east and south <= 35.6812 < north


def test_population_parts_are_added_not_deduplicated():
    rows = [
        ("53394611", "13", "100"),
        ("53394611", "11", "20"),
        ("53394612", "13", "0"),
    ]
    assert MODULE.aggregate_population(rows) == {"53394611": 120, "53394612": 0}
    with pytest.raises(ValueError, match="population"):
        MODULE.aggregate_population([("53394611", "13", "*")])


def test_gamma_posterior_shrinks_zero_and_returns_ordered_interval():
    mean, lo, hi = MODULE.posterior_rate(0, 1000, alpha=2, beta=1)
    assert 0 < lo < mean < hi
    assert mean == pytest.approx(2 / 1.1)
    more = MODULE.posterior_rate(10, 1000, alpha=2, beta=1)
    assert more[0] > mean and more[1] > lo


def test_rank_excludes_small_population_and_uses_lower_bound():
    rows = [
        {"mesh": "a", "accidents": 20, "population": 100},
        {"mesh": "b", "accidents": 8, "population": 2000},
        {"mesh": "c", "accidents": 3, "population": 1000},
    ]
    ranked = MODULE.rank_candidates(rows, 1000, alpha=2, beta=1)
    assert [row["mesh"] for row in ranked] == ["b", "c"]
    assert all(
        row["posterior_low"] <= row["posterior_rate"] <= row["posterior_high"]
        for row in ranked
    )


def test_edge_distance_is_zero_on_boundary_and_large_at_center():
    west, south, east, north = MODULE.mesh_bounds("53394611")
    assert MODULE.edge_distance_m(west, (south + north) / 2) == pytest.approx(0)
    assert MODULE.edge_distance_m((west + east) / 2, (south + north) / 2) > 400


def test_map_class_change_share_matches_hand_counted_example():
    assert MODULE.map_class_change_share([0, 1, 2, 3, 100], 5) == pytest.approx(0.6)


def test_results_csv_uses_lf_line_endings(tmp_path):
    path = tmp_path / "r.csv"
    MODULE.write_results_csv([{"mesh": "53394611", "accidents": 79}], path)
    assert path.read_bytes() == b"mesh,accidents\n53394611,79\n"
