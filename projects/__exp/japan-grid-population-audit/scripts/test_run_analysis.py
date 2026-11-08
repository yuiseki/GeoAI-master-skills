"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with numpy --with pyproj --with pytest pytest -q -p no:cacheprovider test_run_analysis.py"""

# metrics, ranking_rows and the frozen-version check of read_census in run_analysis.py; describe_group and binned of
# run_landcover.py.
import math

import pytest

import run_analysis as ra
import run_landcover as rl

ROWS = [
    {"mesh_code": "a", "census_population": 100, "ghsl_area": 110.0, "ghsl_center": 0.0},
    {"mesh_code": "b", "census_population": 50, "ghsl_area": 40.0, "ghsl_center": 80.0},
    {"mesh_code": "c", "census_population": 0, "ghsl_area": 5.0, "ghsl_center": 1.0},
    {"mesh_code": "d", "census_population": 10, "ghsl_area": 10.0, "ghsl_center": 30.0},
]


def test_metrics_by_hand():
    m = ra.metrics(ROWS, "ghsl_area")
    # deltas +10, -10, +5, 0
    assert m["n"] == 4 and m["census_sum"] == 160 and m["estimate_sum"] == 165
    assert m["estimate_to_census_ratio"] == pytest.approx(165 / 160) and m["bias_mean_people"] == pytest.approx(1.25)
    assert m["mae_people"] == pytest.approx(6.25) and m["median_abs_error_people"] == pytest.approx(7.5)
    assert m["p90_abs_error_people"] == pytest.approx(10.0)
    logs = sorted(abs(math.log1p(e) - math.log1p(c)) for e, c in ((110, 100), (40, 50), (5, 0), (10, 10)))
    assert m["median_abs_log1p_error"] == pytest.approx((logs[1] + logs[2]) / 2)


def test_ranking_rows_top_k_of_each_fraction_and_method():
    out = ra.ranking_rows(ROWS, fractions=(0.25, 0.5))
    assert [(r["fraction"], r["method"], r["k"]) for r in out] == [
        (0.25, "ghsl_area", 1), (0.25, "ghsl_center", 1), (0.5, "ghsl_area", 2), (0.5, "ghsl_center", 2)]
    by = {(r["fraction"], r["method"]): r for r in out}
    assert by[(0.25, "ghsl_area")]["overlap"] == 1 and by[(0.25, "ghsl_center")]["overlap"] == 0   # a vs b
    assert by[(0.5, "ghsl_center")]["overlap"] == 1                    # census {a, b}, center {b, d}
    assert all(r["eligible_meshes"] == 4 for r in out)
    assert ra.ranking_rows(ROWS[:1], fractions=(0.05,))[0]["k"] == 1  # at least one mesh


def test_read_census_refuses_a_table_that_is_not_the_frozen_version():
    class Con:
        def execute(self, sql, params):
            class R:
                @staticmethod
                def fetchall():
                    return [("13", "53394611", "100"), ("11", "53394611", "5")]
            return R()

    with pytest.raises(ValueError, match="frozen version"):
        ra.read_census(Con())


def test_describe_group_and_binned():
    rows = [{"abs_log1p_error": 0.1, "abs_error_people": 3, "census_population": 10, "cover": 0.0},
            {"abs_log1p_error": 0.3, "abs_error_people": 5, "census_population": 20, "cover": 0.5},
            {"abs_log1p_error": 0.5, "abs_error_people": 9, "census_population": 30, "cover": 0.5}]
    assert rl.describe_group([]) == {"n": 0, "median_abs_log1p_error": None, "median_abs_error_people": None}
    b = rl.binned(rows, "cover", [0.0, 0.5, 1.0])
    assert b[0] == {"min_inclusive": 0.0, "max_exclusive": 0.5, "n": 1, "median_abs_log1p_error": 0.1,
                    "median_abs_error_people": 3.0, "census_population_sum": 10}
    assert b[1]["n"] == 2 and b[1]["median_abs_log1p_error"] == pytest.approx(0.4) and b[1]["census_population_sum"] == 50
