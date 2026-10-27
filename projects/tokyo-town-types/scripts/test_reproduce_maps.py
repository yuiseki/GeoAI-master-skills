import csv
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("reproduce_maps.py")
OUTPUTS = SCRIPT.parents[1] / "outputs"


def load_script():
    spec = spec_from_file_location("reproduce_maps", SCRIPT)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_feature_collection_preserves_ids_geometry_and_values():
    module = load_script()
    square = json.dumps(
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
    )
    data = module.feature_collection(["a", "b"], [square, square], [0, 1])
    assert [f["properties"]["id"] for f in data["features"]] == ["a", "b"]
    assert [f["properties"]["value"] for f in data["features"]] == [0, 1]
    assert data["features"][0]["geometry"]["type"] == "Polygon"


def test_feature_collection_rejects_dropped_units():
    module = load_script()
    with pytest.raises(ValueError, match="row count"):
        module.feature_collection(["a", "b"], ["{}"], [0, 1])


def test_generated_maps_have_context_callouts_and_zero_overlaps():
    taito_meta = json.loads((OUTPUTS / "taito-town-types.json").read_text())
    assert taito_meta["n"] == 108
    assert taito_meta["highlights_count"] == 4
    assert taito_meta["roads_count"] > 0
    assert len(taito_meta["labelled_landmarks"]) >= 20
    assert taito_meta["scalebar_m"] == 1000
    assert taito_meta["text_overlaps"] == []

    grid_meta = json.loads((OUTPUTS / "tokyo23-grid-types.json").read_text())
    assert grid_meta["n"] == 631
    assert grid_meta["context_areas_count"] == 23
    assert len(grid_meta["labelled_areas"]) == 23
    assert grid_meta["focus_areas"] == ["台東区の境界 (18格子中15が混在地)"]
    assert grid_meta["highlights_count"] == 1
    assert grid_meta["scalebar_m"] == 5000
    assert grid_meta["text_overlaps"] == []

    pc1_meta = json.loads((OUTPUTS / "taito-street-pc1.json").read_text())
    assert pc1_meta["n"] == 173
    assert pc1_meta["context_areas_count"] == 108
    assert pc1_meta["highlights_count"] == 2
    assert len(pc1_meta["labelled_landmarks"]) >= 20
    assert pc1_meta["scalebar_m"] == 1000
    assert pc1_meta["text_overlaps"] == []

    with (OUTPUTS / "taito-town-clusters.csv").open() as fh:
        town_rows = list(csv.DictReader(fh))
    assert [int(r["n_towns"]) for r in town_rows] == [24, 65, 4, 15]

    with (OUTPUTS / "tokyo23-grid-clusters.csv").open() as fh:
        grid_rows = list(csv.DictReader(fh))
    assert [int(r["n_cells"]) for r in grid_rows] == [225, 37, 225, 1, 103, 40]
    assert [int(r["n_taito_cells"]) for r in grid_rows] == [15, 0, 1, 0, 1, 1]
