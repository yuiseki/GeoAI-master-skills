"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with numpy --with pandas --with shapely --with pytest pytest -q -p no:cacheprovider test_assign_worldpop.py"""

# The 1 km mesh helpers of assign_worldpop.py and of build_inputs.py (one file, as they share mesh_bounds) (mesh_bounds, codes_from_lonlat, aggregate_census).
import numpy as np
import pytest

import assign_worldpop
import build_inputs


def test_codes_from_lonlat_tokyo_station():
    # 35.6812 N, 139.7671 E: lat*1.5 = 53.52 -> 53, lon 139 -> 39; second 4, 6; third 1, 1.
    assert assign_worldpop.codes_from_lonlat(np.array([139.7671]), np.array([35.6812])) == ["53394611"]


@pytest.mark.parametrize("module", [assign_worldpop, build_inputs])
def test_mesh_bounds_round_trip(module):
    w, s, e, n = module.mesh_bounds("53394611")
    assert (e - w, n - s) == pytest.approx((1 / 80, 1 / 120))
    assert w == pytest.approx(139 + 6 / 8 + 1 / 80) and s == pytest.approx(53 / 1.5 + 4 / 12 + 1 / 120)
    # centres of a few meshes map back to their own code
    for code in ("53394611", "53393599", "53390000", "54397079"):
        w, s, e, n = module.mesh_bounds(code)
        assert assign_worldpop.codes_from_lonlat(np.array([(w + e) / 2]), np.array([(s + n) / 2])) == [code]


def test_build_inputs_mesh_bounds_rejects_bad_codes():
    for bad in ("5339461", "5339461x", "533946111"):
        with pytest.raises(ValueError):
            build_inputs.mesh_bounds(bad)


def test_aggregate_census_keeps_tokyo_and_hides_secret_ages():
    rows = [
        ("53394611", "13", "100", "30", "10", "0"),
        ("53394612", "13", "5", "*", "*", "1"),          # secrecy: ages unknown
        ("53394613", "13", "5", "2", "1", "2"),          # secrecy flag != 0 also hides published ages
        ("53394511", "11", "999", "1", "1", "0"),        # not Tokyo
    ]
    out = build_inputs.aggregate_census(rows)
    assert set(out) == {"53394611", "53394612", "53394613"}
    assert out["53394611"] == {"total": 100, "age65": 30, "age75": 10, "secrecy": "0"}
    assert out["53394612"]["age65"] is None and out["53394613"]["age75"] is None


@pytest.mark.parametrize("rows", [
    [("53394611", "13", "10", "1", "1", "0"), ("53394611", "13", "10", "1", "1", "0")],   # duplicate
    [("5339461", "13", "10", "1", "1", "0")],                                              # short code
    [("53394611", "13", "-1", "0", "0", "0")],                                             # negative
    [("53394611", "13", "10", "11", "1", "0")],                                            # 65+ > total
    [("53394611", "13", "10", "2", "3", "0")],                                             # 75+ > 65+
])
def test_aggregate_census_rejects_inconsistent_rows(rows):
    with pytest.raises(ValueError):
        build_inputs.aggregate_census(rows)
