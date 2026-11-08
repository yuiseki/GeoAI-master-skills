"""uvx --python 3.12 --with rasterio --with numpy --with scipy --with pyproj --with pytest pytest -q -p no:cacheprovider test_depth.py"""

# hours, km2, overlap_part, surfaces and the claim rules (judge) of 11_depth.py.
import copy
import importlib

import numpy as np
import pytest

dp = importlib.import_module("11_depth")


def test_hours_since_the_first_gsi_estimate():
    assert dp.hours("0922") == 0 and dp.hours("0924") == 48
    assert dp.hours("s0924") == pytest.approx(51 + 41 / 60)      # 14:00 -> 17:41 two days later
    assert dp.hours("1001") == pytest.approx(9 * 24 + 2)


def test_km2_counts_10m_pixels():
    assert dp.km2(10_000) == 1.0 and dp.km2(5) == 0.0005


def test_overlap_part_picks_the_label_with_most_pixels_in_the_region():
    labels = np.array([[1, 1, 2, 2, 2], [0, 0, 2, 3, 3]])
    region = np.array([[1, 1, 1, 0, 0], [1, 1, 0, 1, 1]], bool)
    assert dp.overlap_part(labels, region) == 1                    # 1 and 3 both have 2 pixels: the lower wins
    region2 = np.array([[0, 1, 1, 1, 0], [0, 0, 1, 0, 0]], bool)
    assert dp.overlap_part(labels, region2) == 2                   # 3 pixels of 2, 1 of 1
    assert dp.overlap_part(labels, np.zeros_like(region)) == 0


def test_overlap_part_tie_goes_to_the_smaller_label():
    labels = np.array([[1, 1, 3, 3]])
    assert dp.overlap_part(labels, np.ones_like(labels, bool)) == 1


def test_surfaces_quantile_rule_per_part():
    labels = np.array([[1, 1, 1, 0], [2, 2, 0, 0]])
    dem = np.array([[1.0, 2.0, 3.0, 9.0], [5.0, 7.0, 9.0, 9.0]])
    s = dp.surfaces(labels, labels > 0, dem, "quantile", q=0.5)
    assert s == {1: pytest.approx(2.0), 2: pytest.approx(6.0)}


GOOD = {"E1": {"mad_m": 0.3, "bias_m": -0.1}, "E2": {"diff_m": 0.1},
        "E3": {f"{lo}-{hi}": {"rate": r} for (lo, hi), r in zip(dp.BANDS, [0.3, 0.6, 0.8, 0.9])},
        "E4": {"max_minus_sat_only_median_m": 0.4},
        "E5": {"gsi_minus_article_m": {"0922": 0.1, "0924": -0.15}, "sat_1006_minus_gsi_1001_m": 0.05},
        "E6": {"sat_1006_in_union_km2": 1.0, "share_in_1001_outline": 0.9, "extrapolated_km2": 0.5},
        "E7": {"called_water_km2": 0.2}}


def test_judge_all_claims_reproduced_at_the_boundaries():
    j = dp.judge(GOOD)
    assert set(j) == {f"D{i}" for i in range(1, 8)} and all(v["reproduced"] for v in j.values())


def test_judge_rules_fail():
    r = copy.deepcopy(GOOD)
    r["E3"]["0.25-0.5"]["rate"] = 0.3                               # not strictly increasing
    r["E2"]["diff_m"] = None
    r["E6"]["share_in_1001_outline"] = None
    j = dp.judge(r)
    assert j["D3"]["conditions"] == {"increasing": False, "shallowest_lt_0.50": True, "deepest_ge_0.85": True}
    assert not j["D2"]["reproduced"] and not j["D6"]["reproduced"]
    assert j["D1"]["reproduced"] and j["D7"]["reproduced"]
