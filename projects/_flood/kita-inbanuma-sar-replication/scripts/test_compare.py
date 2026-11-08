"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with rasterio --with numpy --with scipy --with shapely --with pyproj --with pytest pytest -q -p no:cacheprovider test_compare.py"""

# km2, pct_stats and the claim rules (judge) of 04_compare.py.
import copy
import importlib

import numpy as np
import pytest

cmp_ = importlib.import_module("04_compare")


def test_km2_rounds_square_metres():
    assert cmp_.km2(38e6) == 38.0 and cmp_.km2(1234) == 0.001


def test_pct_stats_medians_per_class():
    ref = np.array([1, 1, 0, 0, 1], bool)
    det = np.array([1, 0, 1, 0, 1], bool)
    valid = np.array([1, 1, 1, 1, 1], bool)
    a = np.array([-10.0, -2.0, -9.0, 0.0, -12.0])
    r = {"det_vv": det, "dvv": a, "dvh": a - 1, "vv_b": a + 1, "vv_a": a + 2, "vh_b": a + 3, "vh_a": a + 4}
    out = cmp_.pct_stats(r, valid, ref)
    assert {k: v["pixels"] for k, v in out.items()} == {"both": 2, "missed": 1, "extra": 1, "neither": 1}
    assert out["both"]["dvv"] == -11.0 and out["both"]["dvh"] == -12.0 and out["missed"]["vh_a"] == 2.0
    valid[3] = False
    assert cmp_.pct_stats(r, valid, ref)["neither"] == {"pixels": 0, "dvv": None, "dvh": None, "vv_b": None,
                                                         "vv_a": None, "vh_b": None, "vh_a": None}


GOOD = {"B1": {"share_det_vv": 0.95},
        "B2": {"recall": 0.5, "precision": 0.8},
        "B3": {"recall_gain": 0.12, "precision_change": -0.01, "missed_ratio": 0.6},
        "B4": {"missed": {"dvh": -5.0, "dvv": -3.0}, "both": {"dvv": -9.0}},
        "B5": {"det_vv_km2": 5.0, "ratio": 1.6}}


def test_judge_all_claims_reproduced():
    j = cmp_.judge(GOOD)
    assert all(v["reproduced"] for v in j.values()) and set(j) == {"A1", "A2", "A3", "A4", "A5"}


@pytest.mark.parametrize("path,value,claim,condition", [
    (("B1", "share_det_vv"), 0.89, "A1", "core_share_ge_0.90"),
    (("B2", "recall"), 0.72, "A2", "recall_41_71"),
    (("B2", "precision"), 0.45, "A2", "recall_lt_precision"),
    (("B3", "missed_ratio"), None, "A3", "missed_ratio_le_0.7"),
    (("B3", "precision_change"), 0.0, "A3", "precision_down"),
    (("B4", "missed", "dvh"), -3.5, "A4", "missed_dvh_1db_below_dvv"),     # only 0.5 dB below dVV
    (("B4", "both", "dvv"), None, "A4", "both_dvv_le_-8"),
    (("B5", "det_vv_km2"), 7.3, "A5", "vv_2.4_7.2"),
    (("B5", "ratio"), None, "A5", "ratio_ge_1.5"),
])
def test_judge_each_rule_fails_alone(path, value, claim, condition):
    b = copy.deepcopy(GOOD)
    d = b
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value
    j = cmp_.judge(b)
    assert j[claim]["conditions"][condition] is False and j[claim]["reproduced"] is False
    assert all(v["reproduced"] for k, v in j.items() if k != claim)
