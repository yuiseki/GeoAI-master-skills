# uvx --from pytest --with 'duckdb>=1.5.5' --with numpy pytest -p no:cacheprovider projects/_traffic_accident/itabashi-accident-trends-by-role/scripts/test_analyze.py
import numpy as np
import pytest

from analyze import (crossing_road, git_head, greedy_hotspots, involves, is_seikatsu, line_angle, party_group,
                     poisson_interval, unit_name, unit_names, ward_ranks)


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
    # (105, the fifth) would have ranked Taito. Itabashi (119) is the 19th of the 23; here it sits fourth, and
    # wards[5] (Taito) has another rank.
    wards = [{"code": c, "share_bike": v, "per_1000": v, "name": c} for c, v in
             [("101", 0.3), ("118", 0.1), ("103", 0.5), ("119", 0.2), ("105", 0.4), ("106", 0.25)]]
    assert ward_ranks(wards, "119") == {"share_bike": 5, "per_1000": 5}
    assert ward_ranks(wards, "106")["share_bike"] == 4
    with pytest.raises(ValueError):
        ward_ranks(wards, "199")
    with pytest.raises(ValueError):
        ward_ranks(wards + wards[:1], "101")


def test_git_head_reads_loose_and_packed_refs(tmp_path):
    # The commit is read from .git without running git: a loose ref first, then packed-refs, None if neither.
    git = tmp_path / ".git"
    (git / "refs/heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    assert git_head(tmp_path) is None
    (git / "packed-refs").write_text("# pack-refs\n" + "b" * 40 + " refs/heads/main\n", encoding="utf-8")
    assert git_head(tmp_path) == "b" * 40
    (git / "refs/heads/main").write_text("a" * 40 + "\n", encoding="utf-8")
    assert git_head(tmp_path) == "a" * 40


def test_line_angle_ignores_the_direction_of_travel():
    assert line_angle((1, 0), (0, 1)) == pytest.approx(90)
    assert line_angle((1, 0), (-1, 0)) == pytest.approx(0)
    assert line_angle((1, 1), (1, 0)) == pytest.approx(45)
    assert line_angle((0, 0), (1, 0)) is None


def test_the_second_road_must_cross_the_first():
    # Shinagawa: OSM names one road 環状六号線 and 山手通り; the nearest two names were that one road, while 中原街道
    # crossed it 3.7 m from the centre. A name running along the first road is skipped; with none crossing, one road.
    near = [("環状六号線", 0.5, (0, 1)), ("山手通り", 1.2, (0.05, 1)), ("中原街道", 3.7, (1, 0.2))]
    assert crossing_road(near) == ("中原街道", 3.7)
    assert crossing_road(near[:2]) == (None, None)
    # A name with no direction near the centre (a piece shorter than a point) cannot be shown to cross.
    assert crossing_road([("昭和通り", 0.0, (1, 0)), ("脇道", 5.0, None)]) == (None, None)
    assert crossing_road([("昭和通り", 0.0, None), ("春日通り", 5.0, (1, 0))]) == ("春日通り", 5.0)


def test_unit_name_names_water_and_nameless_units():
    # Koto's water tract has no S_NAME, Minato's is '‐', Chuo's is 水面調査区: all are HCODE 8154.
    assert unit_name("131061230", "上野三丁目", "8101") == "上野三丁目"
    assert unit_name("131080460", None, "8154") == "水面 (131080460)"
    assert unit_name("131030310", "‐", "8154") == "水面 (131030310)"
    assert unit_name("131020390", "水面調査区", "8154") == "水面 (131020390)"
    assert unit_name("131089990", None, "8101") == "名前なし (131089990)"


def _greedy_by_matrix(xy, radius, k):
    """The first implementation, with the n x n distance matrix: the reference the neighbour lists must match."""
    xy = np.asarray(xy, dtype=float)
    alive = np.ones(len(xy), dtype=bool)
    near = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2) <= radius * radius
    picked = []
    while len(picked) < k and alive.any():
        counts = (near & alive[None, :]).sum(axis=1)
        counts[~alive] = -1
        centre = int(np.argmax(counts))
        members = np.flatnonzero(near[centre] & alive)
        picked.append((centre, members))
        alive[members] = False
    return picked


def test_greedy_hotspots_matches_the_distance_matrix_without_building_it():
    # Ota's 10,335 points made the n x n matrix take about 3.8 GB; the neighbour lists must pick the same centres
    # and members, ties included (points on a 10 m lattice tie often).
    rng = np.random.default_rng(3)
    xy = np.concatenate([rng.normal(0, 300, (1500, 2)), rng.normal(800, 40, (300, 2)),
                         np.round(rng.uniform(-500, 500, (400, 2)) / 10) * 10])
    for radius in (20.0, 30.0, 50.0):
        got = greedy_hotspots(xy, radius, 15)
        want = _greedy_by_matrix(xy, radius, 15)
        assert [c for c, _ in got] == [c for c, _ in want]
        assert all(np.array_equal(a, b) for (_, a), (_, b) in zip(got, want))


def test_greedy_hotspots_runs_on_many_points():
    # 60,000 points: the matrix would need 3.6e9 cells; the neighbour lists finish in seconds.
    rng = np.random.default_rng(5)
    picked = greedy_hotspots(rng.uniform(0, 20000, (60000, 2)), 30.0, 15)
    assert len(picked) == 15


def test_unit_names_tell_apart_units_of_one_name():
    # Ota's 令和島 is two KEY_CODE; towns.csv showed two rows named 令和島.
    got = unit_names([("131110811", "令和島"), ("131110812", "令和島"), ("131110010", "大森本町一丁目")])
    assert got == {"131110811": "令和島 (131110811)", "131110812": "令和島 (131110812)", "131110010": "大森本町一丁目"}
