"""uvx --with pytest pytest test_robustness_grid.py"""

import sys

import pytest

from robustness_grid import check_claim, extract, grid, run_grid


def test_grid_is_every_combination():
    g = grid(["a=1,2", "b=x,y,z"])
    assert len(g) == 6
    assert {"a": "1", "b": "z"} in g


def test_extract_takes_the_first_group_of_each_pattern():
    out = "linear  r2 0.6274 (sd 0.0085)\nhgb  r2 0.5762 (sd 0.024)\n"
    vals = extract(out, ["linear=^linear .*r2 ([-0-9.]+)", "hgb=^hgb .*r2 ([-0-9.]+)"])
    assert vals == {"linear": 0.6274, "hgb": 0.5762}


def test_a_pattern_that_finds_nothing_is_an_error_not_a_skip():
    with pytest.raises(SystemExit):
        extract("nothing here", ["linear=^linear .*r2 ([-0-9.]+)"])


def test_claims_compare_extracted_numbers():
    assert check_claim("linear > hgb", {"linear": 0.6, "hgb": 0.5}) is True
    assert check_claim("linear - hgb > 0.2", {"linear": 0.6, "hgb": 0.5}) is False
    assert check_claim("abs(i) < 0.05 and p > 0.05", {"i": 0.01, "p": 0.3}) is True


def test_claims_cannot_run_arbitrary_code():
    with pytest.raises(SystemExit):
        check_claim("__import__('os').system('true')", {})
    with pytest.raises(SystemExit):
        check_claim("linear.real > 0", {"linear": 1.0})


def test_run_grid_substitutes_runs_and_tabulates(tmp_path):
    py = sys.executable
    steps = [f"{py} -c \"print('score', {{a}} * {{b}})\""]
    rows = run_grid(steps, grid(["a=1,3", "b=2,5"]), ["score=^score ([-0-9.]+)"], "score > 5")
    assert [(r["vary"]["a"], r["vary"]["b"], r["values"]["score"], r["holds"]) for r in rows] == [
        ("1", "2", 2.0, False), ("1", "5", 5.0, False), ("3", "2", 6.0, True), ("3", "5", 15.0, True)]


def test_a_failing_command_stops_the_grid():
    with pytest.raises(SystemExit):
        run_grid([f"{sys.executable} -c \"import sys; sys.exit(3)\""], [{}], [], "True")
