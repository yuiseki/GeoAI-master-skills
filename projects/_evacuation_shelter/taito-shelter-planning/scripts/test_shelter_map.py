"""Regression tests for the shelter-demand choropleth and siting maps."""

import csv
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("reproduce_map", Path(__file__).with_name("reproduce_map.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"


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


def test_generated_shelter_maps_and_selected_sites_csv():
    density_meta = json.loads((OUTPUTS / "taito-population-density.json").read_text())
    assert density_meta["n"] == 108
    assert density_meta["kind"] == "sequential"
    assert density_meta["class_changes"]["equal"] == 0.306
    assert density_meta["highlights_count"] == 4
    assert len(density_meta["labelled_landmarks"]) >= 20
    assert density_meta["scalebar_m"] == 1000
    assert density_meta["text_overlaps"] == []

    siting_meta = json.loads((OUTPUTS / "taito-shelter-siting.json").read_text())
    assert siting_meta["n"] == 108
    assert [pg["count"] for pg in siting_meta["point_groups"]] == [503, 63, 13, 13]
    assert len(siting_meta["labelled_landmarks"]) >= 20
    assert siting_meta["scalebar_m"] == 1000
    assert siting_meta["text_overlaps"] == []

    with (OUTPUTS / "selected-sites.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 52

    existing_meta = json.loads((OUTPUTS / "taito-existing-shelters.json").read_text())
    assert existing_meta["n"] == 108
    assert [pg["count"] for pg in existing_meta["point_groups"]] == [14, 3]
    assert existing_meta["scalebar_m"] == 1000
    assert existing_meta["text_overlaps"] == []

    with (OUTPUTS / "existing-shelters.csv").open() as fh:
        ex_rows = list(csv.DictReader(fh))
    assert len(ex_rows) == 17
