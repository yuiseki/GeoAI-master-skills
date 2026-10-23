import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("reproduce_maps.py")


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
