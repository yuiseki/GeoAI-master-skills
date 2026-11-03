# uvx --from 'duckdb>=1.5.5' --with numpy --with pytest pytest projects/_traffic_accident/taito-accident-trends-by-role/scripts/test_analyze.py
import numpy as np
import pytest

from analyze import greedy_hotspots, involves, is_seikatsu, party_group, poisson_interval, ward_ranks


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


def test_ward_ranks_find_the_ward_by_its_code_not_its_place():
    # The rank was read from wards[5], the sixth ward in code order. That is Taito (106), but a copy for Bunkyo
    # (105, the fifth) would have ranked Taito.
    wards = [{"code": c, "share_bike": v, "per_1000": v, "name": c} for c, v in
             [("101", 0.3), ("102", 0.1), ("103", 0.5), ("104", 0.2), ("105", 0.4), ("106", 0.25)]]
    assert ward_ranks(wards, "106") == {"share_bike": 4, "per_1000": 4}
    assert ward_ranks(wards, "105")["share_bike"] == 2
    with pytest.raises(ValueError):
        ward_ranks(wards, "199")
    with pytest.raises(ValueError):
        ward_ranks(wards + wards[:1], "101")
