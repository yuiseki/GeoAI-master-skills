"""uvx --with numpy --with duckdb --with pytest pytest test_accessibility.py"""

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from accessibility import fca, hansen, matrix_from_pairs, regional_ratio, weight

INF = np.inf
# 3 demand points, 2 facilities. Catchment 10: facility 0 reaches origins 0 and 1, facility 1 reaches 1 and 2.
P = np.array([100.0, 200.0, 100.0])
S = np.array([10.0, 6.0])
C = np.array([[5.0, 20.0], [8.0, 9.0], [30.0, 4.0]])


def test_two_step_known_answer():
    r = fca(P, S, C, lambda d: weight(d, "binary", 10))
    assert r["ratio"].tolist() == pytest.approx([10 / 300, 6 / 300])
    assert r["access"].tolist() == pytest.approx([10 / 300, 10 / 300 + 6 / 300, 6 / 300])


def test_supply_is_conserved_over_demand():
    rng = np.random.default_rng(0)
    p, s = rng.integers(1, 500, 40).astype(float), rng.uniform(1, 20, 7)
    c = rng.uniform(0, 30, (40, 7))
    for kind in ("binary", "linear", "gaussian"):
        r = fca(p, s, c, lambda d: weight(d, kind, 12))
        allocated = s[r["demand_in_catchment"] > 0].sum()
        assert (p * r["access"]).sum() == pytest.approx(allocated)


def test_competition_makes_a_nearer_facility_worth_less():
    # Origin 0 is 1 away from a facility shared with 1,000 others; origin 2 is 9 away from one it has alone.
    p = np.array([10.0, 1000.0, 10.0])
    c = np.array([[1.0, INF], [1.0, INF], [INF, 9.0]])
    r = fca(p, np.array([5.0, 5.0]), c, lambda d: weight(d, "binary", 10))
    assert r["nearest"][0] < r["nearest"][2]
    assert r["access"][0] < r["access"][2]  # reachable is not the same as accessible


def test_status_separates_unreachable_from_outside_every_catchment():
    c = np.array([[5.0], [50.0], [INF]])
    r = fca(np.array([1.0, 1.0, 1.0]), np.array([2.0]), c, lambda d: weight(d, "binary", 10))
    assert r["status"].tolist() == ["served", "no_facility_in_catchment", "unreachable"]
    assert r["access"].tolist() == pytest.approx([2.0, 0.0, 0.0])


def test_a_facility_with_no_demand_in_reach_is_reported_not_spread():
    c = np.array([[5.0, 50.0]])
    r = fca(np.array([10.0]), np.array([3.0, 4.0]), c, lambda d: weight(d, "binary", 10))
    assert r["facility_status"].tolist() == ["allocated", "no_demand_in_catchment"]
    assert math.isnan(r["ratio"][1])
    assert r["access"][0] == pytest.approx(0.3)


def test_step_weights_follow_the_enhanced_definition():
    # Weights 1 within 6, 0.5 within 10: facility 0 sees origin 0 at 5 (1) and origin 1 at 8 (0.5).
    w = lambda d: weight(d, "steps", 10, steps=[(6, 1.0), (10, 0.5)])
    r = fca(P, S, C, w)
    d0 = 100 * 1 + 200 * 0.5
    d1 = 200 * 0.5 + 100 * 1
    assert r["ratio"].tolist() == pytest.approx([10 / d0, 6 / d1])
    assert r["access"][1] == pytest.approx(0.5 * 10 / d0 + 0.5 * 6 / d1)


def test_gaussian_weight_is_one_at_zero_and_zero_at_the_catchment_edge():
    d = np.array([0.0, 5.0, 10.0, 11.0])
    w = weight(d, "gaussian", 10)
    assert w[0] == pytest.approx(1) and w[2] == pytest.approx(0) and w[3] == 0
    assert w[1] == pytest.approx((math.exp(-0.125) - math.exp(-0.5)) / (1 - math.exp(-0.5)))
    assert weight(np.array([7.5]), "linear", 10)[0] == pytest.approx(0.25)


def test_hansen_gravity_has_no_competition():
    a = hansen(S, C, lambda d: weight(d, "power", None, beta=1.0))
    assert a.tolist() == pytest.approx([10 / 5 + 6 / 20, 10 / 8 + 6 / 9, 10 / 30 + 6 / 4])


def test_power_decay_refuses_a_zero_cost():
    with pytest.raises(SystemExit, match="zero"):
        weight(np.array([0.0, 2.0]), "power", None, beta=1.0)


def test_regional_ratio_is_supply_over_demand_inside_each_region():
    out = regional_ratio(P, np.array(["a", "a", "b"]), S, np.array(["a", "b"]))
    assert out == {"a": pytest.approx(10 / 300), "b": pytest.approx(6 / 100)}


def test_a_larger_catchment_changes_who_is_served():
    small = fca(P, S, C, lambda d: weight(d, "binary", 6))
    large = fca(P, S, C, lambda d: weight(d, "binary", 25))
    assert small["status"][1] == "no_facility_in_catchment" and large["status"][1] == "served"


def test_matrix_from_pairs_marks_missing_pairs_unreachable_and_stops_on_bad_rows():
    m = matrix_from_pairs(["o1", "o2"], ["f1"], [("o1", "f1", 3.0)])
    assert m[0, 0] == 3 and m[1, 0] == INF
    for bad in ([("o1", "f1", 3.0), ("o1", "f1", 4.0)], [("o9", "f1", 3.0)], [("o1", "f1", -1.0)],
                [("o1", "f1", float("nan"))]):
        with pytest.raises(SystemExit):
            matrix_from_pairs(["o1", "o2"], ["f1"], bad)


def _csv(path, header, rows):
    path.write_text(header + "\n" + "\n".join(",".join(map(str, r)) for r in rows) + "\n")
    return str(path)


def test_cli_reports_counts_conservation_and_only_the_reported_origins(tmp_path):
    o = _csv(tmp_path / "o.csv", "id,people,interior", [("o1", 100, "true"), ("o2", 200, "true"), ("o3", 100, "false")])
    f = _csv(tmp_path / "f.csv", "id,beds", [("f1", 10), ("f2", 6)])
    m = _csv(tmp_path / "m.csv", "origin,facility,cost", [("o1", "f1", 5), ("o1", "f2", 20), ("o2", "f1", 8),
                                                          ("o2", "f2", 9), ("o3", "f2", 4), ("o3", "f1", 30)])
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("accessibility.py")), o, f, m,
                          "--demand", "people", "--supply", "beds", "--catchment", "10", "--report", "interior",
                          "--sensitivity", "6", "25", "--out", str(tmp_path / "a.csv")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "origins 3: served 3, no_facility_in_catchment 0, unreachable 0" in out.stdout
    assert "supply 16 = allocated 16 + unallocated 0" in out.stdout
    assert "reported origins 2 of 3" in out.stdout
    assert "catchment 6:" in out.stdout and "catchment 25:" in out.stdout
    assert (tmp_path / "a.csv").exists() and (tmp_path / "a.facilities.csv").exists()
