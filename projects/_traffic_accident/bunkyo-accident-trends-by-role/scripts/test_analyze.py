# uvx --from 'duckdb>=1.5.5' --with numpy --with pytest pytest projects/_traffic_accident/bunkyo-accident-trends-by-role/scripts/test_analyze.py
import numpy as np
import pytest

from analyze import CITY, WARD, greedy_hotspots, involves, is_seikatsu, party_group, poisson_interval, ward_ranks


def test_seikatsu_strict_and_broad():
    assert is_seikatsu("01") and is_seikatsu("02") and is_seikatsu("11")
    assert not is_seikatsu("14") and is_seikatsu("14", broad=True)
    assert is_seikatsu("17", broad=True)
    # 5.5 m or wider single roads and medium x medium crossings are not 生活道路 in either reading.
    for width in ("03", "04", "15", "19", "00"):
        assert not is_seikatsu(width) and not is_seikatsu(width, broad=True)


def test_involves_looks_at_both_parties_and_age():
    row = {"type_A": "03", "age_A": "45", "type_B": "61", "age_B": "75"}
    assert involves(row, {"61"})
    assert involves(row, {"61"}, {"65", "75"})
    assert not involves(row, {"61"}, {"01"})
    # The age must belong to the same party as the type: A is 45, B is the pedestrian.
    row = {"type_A": "61", "age_A": "45", "type_B": "03", "age_B": "75"}
    assert not involves(row, {"61"}, {"65", "75"})


def test_party_group_splits_business_cars():
    assert party_group("03", "01") == "乗用車 (事業用)"
    assert party_group("03", "31") == "乗用車 (自家用)"
    assert party_group("52", "41") == "自転車"
    assert party_group("00", "00") == "その他・不明"


def test_greedy_hotspots_picks_densest_and_does_not_reuse():
    # Five points at one corner, three 100 m away, one alone.
    xy = [(0, 0), (5, 0), (0, 5), (3, 3), (-4, 1), (100, 0), (104, 0), (100, 6), (500, 500)]
    picked = greedy_hotspots(xy, 30, 3)
    assert [len(m) for _, m in picked] == [5, 3, 1]
    members = np.concatenate([m for _, m in picked])
    assert len(members) == len(set(members)) == 9


def test_greedy_hotspots_radius_matters():
    xy = [(0, 0), (25, 0), (50, 0)]
    assert [len(m) for _, m in greedy_hotspots(xy, 30, 3)] == [3]
    assert [len(m) for _, m in greedy_hotspots(xy, 20, 3)] == [1, 1, 1]


def test_poisson_interval_known_values():
    # Garwood 95% interval: n=0 -> (0, 3.689), n=10 -> (4.795, 18.390).
    assert poisson_interval(0) == pytest.approx((0, 3.689), abs=1e-3)
    assert poisson_interval(10) == pytest.approx((4.795, 18.390), abs=1e-3)


def test_ward_ranks_follow_the_code_not_the_row_order():
    # Bunkyo (105) is the 5th of the 23 wards in code order; Taito's script used wards[5], the 6th row.
    # Shuffle the rows: the rank must still be Bunkyo's.
    wards = [{"code": f"{c:03d}", "share_bike": 0.0, "per_1000": 0.0} for c in range(101, 124)]
    by_code = {w["code"]: w for w in wards}
    by_code["105"].update(share_bike=0.5, per_1000=1.0)  # Bunkyo: highest bike share
    by_code["106"].update(share_bike=0.9, per_1000=0.5)  # Taito: higher still, so Bunkyo is 2nd
    by_code["101"].update(per_1000=2.0)
    shuffled = wards[::-1]
    assert ward_ranks(wards, "105") == ward_ranks(shuffled, "105") == {"share_bike": 2, "per_1000": 2}
    assert ward_ranks(wards, "106")["share_bike"] == 1
    assert CITY == "105" and WARD == "13105"
    with pytest.raises(ValueError):
        ward_ranks(wards, "999")
