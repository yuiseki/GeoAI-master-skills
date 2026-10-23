# uvx --with matplotlib --with numpy --with pytest pytest scripts/test_spatial_result_map.py  # noqa: E501
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("spatial_result_map.py")


def fixture(tmp_path, values):
    features = []
    for i, value in enumerate(values):
        features.append(
            {
                "type": "Feature",
                "properties": {"id": str(i), "value": value},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[i, 0], [i + 0.9, 0], [i + 0.9, 1], [i, 1], [i, 0]]
                    ],
                },
            }
        )
    input_path = tmp_path / "input.geojson"
    input_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features})
    )
    return input_path


def run(tmp_path, config, values):
    input_path = fixture(tmp_path, values)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False))
    output = tmp_path / "map.png"
    result = subprocess.run(
        [sys.executable, SCRIPT, input_path, config_path, output],
        capture_output=True,
        text=True,
    )
    return result, output


BASE = {
    "question": "どこにどの類型があるか",
    "value": "value",
    "crs": "OGC:CRS84",
    "source": "synthetic-test",
    "data_version": "test",
    "unit": "地区",
}


def test_category_map_has_named_counts_and_nodata(tmp_path):
    config = BASE | {
        "kind": "category",
        "categories": {"0": "住宅", "1": "商業"},
    }
    result, output = run(tmp_path, config, [0, 1, 1, None])
    assert result.returncode == 0, result.stderr
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    metadata = json.loads(output.with_suffix(".json").read_text())
    assert metadata["counts"] == {"住宅": 1, "商業": 2}
    assert metadata["nodata"] == 1
    assert metadata["n"] == 4
    assert metadata["font"]


def test_unknown_category_stops_instead_of_mislabeling(tmp_path):
    config = BASE | {"kind": "category", "categories": {"0": "住宅"}}
    result, output = run(tmp_path, config, [0, 1])
    assert result.returncode != 0
    assert "unlabelled category" in result.stderr
    assert not output.exists()


def test_category_palette_stops_before_reusing_a_colour(tmp_path):
    config = BASE | {
        "kind": "category",
        "categories": {str(i): f"型{i}" for i in range(7)},
    }
    result, output = run(tmp_path, config, list(range(7)))
    assert result.returncode != 0
    assert "palette supports" in result.stderr
    assert not output.exists()


def test_diverging_scale_is_symmetric_and_preserves_zero(tmp_path):
    config = BASE | {"kind": "diverging", "negative": "整備", "positive": "電柱"}
    result, output = run(tmp_path, config, [-2.0, 0.0, 4.0])
    assert result.returncode == 0, result.stderr
    metadata = json.loads(output.with_suffix(".json").read_text())
    assert metadata["scale"] == [-4.0, 4.0]
    assert metadata["nodata"] == 0
    assert metadata["n"] == 3


def test_outline_and_provenance_are_recorded(tmp_path):
    config = BASE | {
        "kind": "category",
        "categories": {"0": "住宅"},
        "source_commit": "abc123",
        "method": "k-means k=1",
        "outline": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        },
    }
    result, output = run(tmp_path, config, [0])
    assert result.returncode == 0, result.stderr
    metadata = json.loads(output.with_suffix(".json").read_text())
    assert metadata["outline"] is True
    assert metadata["source_commit"] == "abc123"
    assert metadata["method"] == "k-means k=1"
