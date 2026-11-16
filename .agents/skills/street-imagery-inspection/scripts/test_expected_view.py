"""uvx --with shapely --with pytest pytest test_expected_view.py

Worked by hand for a level view 1,000 x 1,000 px with a horizontal angle of view of 90 degrees: f = 500 px, the
centre row c = 500. A camera 2.5 m above the ground at (0, 0) looks north (+y). A pole 8 m tall at (0, 10) is 10 m
deep: its foot is at row 500 + 500 * 2.5 / 10 = 625, its top at 500 - 500 * (8 - 2.5) / 10 = 225, so 400 px tall.
At (0, 40) it is 100 px tall (531.25 to 431.25). At (5, 10) it is 26.57 degrees off the axis and still 10 m deep
(11.18 * cos 26.57), so again 400 px. At (20, 10) it is 63.4 degrees off the axis, outside the 45-degree half angle.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from expected_view import View, expect  # noqa: E402

V = View(x=0, y=0, azimuth=0, hfov=90, width=1000, height=1000, camera_height=2.5)


def test_a_near_pole_ahead_should_be_seen_and_its_size_is_computed():
    r = expect(V, 0, 10, 8)
    assert r["verdict"] == "should_be_visible"
    assert r["foot_row"] == pytest.approx(625) and r["top_row"] == pytest.approx(225)
    assert r["apparent_px"] == pytest.approx(400)
    # off the axis, the depth (not the distance) sets the size
    assert expect(V, 5, 10, 8)["apparent_px"] == pytest.approx(400)


def test_far_aside_behind_and_too_small_are_not_evidence_of_absence():
    assert expect(V, 0, 40, 8)["reasons"] == ["too_small"]           # 100 px < 15% of 1,000 px
    assert expect(V, 0, 40, 8, min_px=80)["verdict"] == "should_be_visible"
    assert expect(V, 20, 10, 8)["reasons"] == ["out_of_frame"]
    assert expect(V, 0, -10, 8)["reasons"] == ["out_of_frame"]
    assert expect(V, 0, 500, 8, max_distance=100)["reasons"] == ["too_far", "too_small"]


def test_a_pole_cut_by_the_frame_is_clipped_and_its_foot_flagged():
    r = expect(V, 0, 2, 8)
    assert r["apparent_px"] == pytest.approx(1000) and r["foot_in_frame"] is False


def test_a_building_on_the_sight_line_hides_the_pole():
    wall = box(-1, 4, 1, 6)
    assert expect(V, 0, 10, 8, occluders=[wall])["reasons"] == ["occluded"]
    assert expect(V, 0, 10, 8, occluders=[box(5, 4, 7, 6)])["verdict"] == "should_be_visible"
    # the building the pole stands in front of, beyond it, does not hide it
    assert expect(V, 0, 10, 8, occluders=[box(-1, 12, 1, 14)])["verdict"] == "should_be_visible"


def test_command_line_counts_only_targets_that_some_view_should_show(tmp_path):
    views = tmp_path / "views.csv"
    views.write_text("view_id,x,y,azimuth,hfov,width,height\nv1,0,0,0,90,1000,1000\nv2,0,0,90,90,1000,1000\n")
    targets = tmp_path / "poles.csv"
    targets.write_text("id,x,y\nnear,0,10\neast,10,0\nfar,0,60\nhidden,0,-10\n")
    seen = tmp_path / "detected.csv"
    seen.write_text("id\nnear\n")
    walls = tmp_path / "walls.json"
    walls.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [[[4, -1], [6, -1], [6, 1], [4, 1], [4, -1]]]}}]}))
    out = tmp_path / "expected.csv"
    args = [views, targets, "--target-height", 8,
            "--camera-height", 2.5, "--occluders", walls, "--detected", seen, "--out", out]
    r = subprocess.run([sys.executable, str(HERE / "expected_view.py"), *map(str, args)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout)
    # near: seen from v1; east: behind a wall from v2; far: too small; hidden: behind the camera in v1, out of v2
    assert s["targets"] == 4 and s["should_be_visible"] == 1 and s["detected_of_visible"] == 1
    assert s["not_visible_reasons"] == {"occluded": 1, "too_small": 1, "out_of_frame": 1}
    r = subprocess.run([sys.executable, str(HERE / "expected_view.py"), *map(str, args), "--max-distance", "50"],
                       capture_output=True, text=True)
    assert json.loads(r.stdout)["not_visible_reasons"] == {"occluded": 1, "too_far": 1, "out_of_frame": 1}
    rows = out.read_text().splitlines()
    assert rows[0] == "id,verdict,views,reasons,detected" and "near,should_be_visible,v1,,1" in rows
