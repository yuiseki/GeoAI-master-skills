# uvx --with matplotlib --with pytest pytest scripts/test_result_figures.py
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("result_figures.py")


def run(tmp_path, data):
    source = tmp_path / "input.json"
    output = tmp_path / "figure.png"
    source.write_text(json.dumps(data, ensure_ascii=False))
    result = subprocess.run(
        [sys.executable, SCRIPT, source, output], check=False, capture_output=True, text=True
    )
    return result, output


def test_pareto_preserves_all_points_and_method_membership(tmp_path):
    data = {
        "kind": "pareto",
        "question": "被覆と浸水の両立",
        "source": "synthetic",
        "data_version": "test",
        "x_label": "浸水ランク",
        "y_label": "被覆人口 (人)",
        "x_direction": "min",
        "y_direction": "max",
        "points": [
            {"x": 0, "y": 10, "methods": ["epsilon", "weighted"]},
            {"x": 1, "y": 12, "methods": ["epsilon"]},
            {"x": 2, "y": 20, "methods": ["epsilon", "weighted"]},
        ],
    }
    result, output = run(tmp_path, data)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes().startswith(b"\x89PNG")
    meta = json.loads(output.with_suffix(".json").read_text())
    assert meta["n"] == 3
    assert meta["method_counts"] == {"epsilon": 3, "weighted": 2}
    assert meta["x_range"][0] <= 0
    assert meta["y_range"][0] <= 10


def test_pareto_rejects_dominated_point(tmp_path):
    data = {
        "kind": "pareto", "question": "test", "source": "synthetic",
        "data_version": "test", "x_label": "x", "y_label": "y",
        "x_direction": "min", "y_direction": "max",
        "points": [{"x": 0, "y": 10, "methods": ["epsilon"]},
                   {"x": 1, "y": 9, "methods": ["epsilon"]}],
    }
    result, output = run(tmp_path, data)
    assert result.returncode != 0
    assert "dominated" in result.stderr
    assert not output.exists()


def test_schedule_preserves_intervals_and_groups(tmp_path):
    data = {
        "kind": "schedule", "question": "各車両がいつ走るか",
        "source": "synthetic", "data_version": "test",
        "x_label": "時刻", "y_label": "車両", "time_unit": "seconds",
        "intervals": [
            {"group": "車両1", "start": 8 * 3600, "end": 9 * 3600, "kind": "運行"},
            {"group": "車両1", "start": 10 * 3600, "end": 11 * 3600, "kind": "運行"},
            {"group": "車両2", "start": 8 * 3600, "end": 10 * 3600, "kind": "運行"},
        ],
    }
    result, output = run(tmp_path, data)
    assert result.returncode == 0, result.stderr
    meta = json.loads(output.with_suffix(".json").read_text())
    assert meta["n"] == 3
    assert meta["groups"] == 2
    assert meta["time_range"] == [8 * 3600, 11 * 3600]
    # a report quotes the clock time, so the output holds it as written, not only as seconds
    assert meta["time_range_clock"] == ["08:00", "11:00"]


def test_schedule_rejects_overlapping_intervals_in_one_group(tmp_path):
    data = {
        "kind": "schedule", "question": "test", "source": "synthetic",
        "data_version": "test", "x_label": "x", "y_label": "y",
        "time_unit": "seconds",
        "intervals": [
            {"group": "1", "start": 1, "end": 3, "kind": "trip"},
            {"group": "1", "start": 2, "end": 4, "kind": "trip"},
        ],
    }
    result, output = run(tmp_path, data)
    assert result.returncode != 0
    assert "overlap" in result.stderr
    assert not output.exists()
