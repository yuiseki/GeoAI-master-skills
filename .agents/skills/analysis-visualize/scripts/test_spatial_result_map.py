# uvx --with matplotlib --with numpy --with pytest pytest scripts/test_spatial_result_map.py  # noqa: E501
import json
import subprocess
import sys
from pathlib import Path

from spatial_result_map import _interior_point

SCRIPT = Path(__file__).with_name("spatial_result_map.py")


def fixture(tmp_path, values):
    features = []
    for i, value in enumerate(values):
        features.append(
            {
                "type": "Feature",
                "properties": {"id": str(i), "value": value, "name": f"地区{i}"},
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


def test_interior_point_lies_inside_concave_u_polygon():
    # A U-shaped polygon whose centroid (5, 4.2) lies in the empty bay (2 < x < 8, y > 2)
    u_ring = [
        [0, 0],
        [10, 0],
        [10, 10],
        [8, 10],
        [8, 2],
        [2, 2],
        [2, 10],
        [0, 10],
        [0, 0],
    ]
    px, py = _interior_point([[u_ring]])
    assert 0 < px < 10 and 0 < py < 10
    assert not (2 < px < 8 and py > 2)


def test_context_roads_landmarks_highlights_and_scalebar(tmp_path):
    config = BASE | {
        "kind": "category",
        "categories": {"0": "住宅", "1": "商業"},
        "expect_units": 3,
        "context_areas": [
            {
                "name": "西部区",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1.5, 0], [1.5, 1], [0, 1], [0, 0]]],
                },
            },
            {
                "name": "東部区",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1.5, 0], [3, 0], [3, 1], [1.5, 1], [1.5, 0]]],
                },
            },
        ],
        "roads": [
            {
                "tier": "major",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, 0.5], [3, 0.5]],
                },
            }
        ],
        "focus_areas": [
            {
                "name": "注目区域",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }
        ],
        "highlights": [{"id": "2", "label": "代表地区", "rank": "1"}],
        "landmarks": [
            {"name": "中央駅", "coordinates": [0.5, 0.5]},
            {"name": "東公園", "coordinates": [0.5, 0.5]},
        ],
        "stop_on_overlap": True,
    }
    result, output = run(tmp_path, config, [0, 1, 1])
    assert result.returncode == 0, result.stderr
    metadata = json.loads(output.with_suffix(".json").read_text())
    assert metadata["context_areas_count"] == 2
    assert sorted(metadata["labelled_areas"]) == ["東部区", "西部区"]
    assert metadata["roads_count"] == 1
    assert sorted(metadata["labelled_landmarks"]) == ["中央駅", "東公園"]
    assert metadata["focus_areas"] == ["注目区域"]
    assert metadata["highlights_count"] == 1
    assert metadata["scalebar_m"] > 0
    assert metadata["text_overlaps"] == []


def test_unknown_highlight_id_or_wrong_unit_count_stops(tmp_path):
    bad_hl = BASE | {
        "kind": "category",
        "categories": {"0": "住宅"},
        "highlights": [{"id": "99", "label": "不明", "rank": "1"}],
    }
    result, output = run(tmp_path, bad_hl, [0, 0])
    assert result.returncode != 0
    assert "highlighted id not found" in result.stderr
    assert not output.exists()

    bad_count = BASE | {
        "kind": "category",
        "categories": {"0": "住宅"},
        "expect_units": 5,
    }
    result2, output2 = run(tmp_path, bad_count, [0, 0])
    assert result2.returncode != 0
    assert "expected 5 units" in result2.stderr
    assert not output2.exists()
