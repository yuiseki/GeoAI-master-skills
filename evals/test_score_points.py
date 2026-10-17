"""Tests for score_points.py: one-to-one matching of predicted points to answer points within a radius."""

import json
import subprocess
from pathlib import Path

import pytest

from score_points import match, read_points

HERE = Path(__file__).parent

# about 0.0009 degrees of latitude is 100 m
TRUTH = [("a", 139.70, 35.70), ("b", 139.80, 35.70), ("c", 139.90, 35.70)]


def test_a_prediction_matches_only_one_answer_point():
    # two predictions next to the same answer point count once; the second is a false positive
    preds = [(139.70, 35.7001), (139.70, 35.7002)]
    r = match(preds, TRUTH, radius_m=100)
    assert (r["matched"], r["n_pred"], r["n_truth"]) == (1, 2, 3)
    assert r["precision"] == 0.5 and r["recall"] == pytest.approx(1 / 3)


def test_the_radius_is_in_metres():
    near = [(139.80, 35.70 + 0.0008)]   # about 89 m north
    far = [(139.80, 35.70 + 0.0010)]    # about 111 m north
    assert match(near, TRUTH, radius_m=100)["matched"] == 1
    assert match(far, TRUTH, radius_m=100)["matched"] == 0


def test_closest_pairs_are_taken_first():
    # one prediction between a and a second prediction: the closer pair wins, so both answers can be matched
    truth = [("a", 139.700, 35.70), ("b", 139.701, 35.70)]   # about 90 m apart
    preds = [(139.7004, 35.70), (139.7011, 35.70)]
    r = match(preds, truth, radius_m=100)
    assert r["matched"] == 2 and r["missed"] == []


def test_missed_answer_points_are_listed():
    r = match([(139.70, 35.70)], TRUTH, radius_m=100)
    assert r["missed"] == ["b", "c"]


def test_no_predictions_scores_zero_without_dividing_by_zero():
    r = match([], TRUTH, radius_m=100)
    assert (r["precision"], r["recall"], r["f1"]) == (0.0, 0.0, 0.0)


def test_read_points_refuses_swapped_axes(tmp_path):
    # latitude in the lon column is the usual mistake; Japan's longitudes are 122-154
    f = tmp_path / "p.csv"
    f.write_text("lon,lat\n35.70,139.70\n")
    with pytest.raises(SystemExit, match="lon"):
        read_points(f)


def test_read_points_accepts_longitude_latitude_headers(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("name,longitude,latitude\nx,139.7,35.7\n")
    assert read_points(f) == [(139.7, 35.7)]


def test_command_line_prints_json(tmp_path):
    p = tmp_path / "p.csv"
    p.write_text("lon,lat\n139.70,35.70\n")
    t = tmp_path / "t.csv"
    t.write_text("id,lon,lat\n" + "".join(f"{i},{x},{y}\n" for i, x, y in TRUTH))
    out = subprocess.run(["python", str(HERE / "score_points.py"), str(p), str(t), "--radius", "100"],
                         check=True, capture_output=True, text=True).stdout
    r = json.loads(out)
    assert r["matched"] == 1 and r["radius_m"] == 100
