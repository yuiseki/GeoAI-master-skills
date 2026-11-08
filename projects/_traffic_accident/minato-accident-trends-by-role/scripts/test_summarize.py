"""uvx --python 3.12 --with pytest pytest -q -p no:cacheprovider test_summarize.py"""

# summarize.py is copied into every *-accident-trends-by-role ward and grew ward-specific lines; this test is the same
# file in each ward. It feeds a superset of the CSV columns any copy reads, points the module's OUT at tmp_path, and
# checks the lines every copy prints against counts worked out by hand.
import csv
import json
import re
from pathlib import Path

import pytest

import summarize

SOURCE = Path(summarize.__file__).read_text(encoding="utf-8")


def ward_name():
    if hasattr(summarize, "WARD_NAME"):
        return summarize.WARD_NAME
    named = [n for n in re.findall(r'"([^"\s]+区)"', SOURCE) if n != "23区"]
    return named[0] if named else "テスト区"


def write(out, name, header, rows):
    with (out / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def lines(tmp_path, monkeypatch):
    ward = ward_name()
    # Hours 5 and 19 sit on the night-window edges, 6 just outside; pedestrian ages are read from whichever party
    # is the pedestrian (age_B in row 1, age_A in row 2).
    write(tmp_path, "deaths.csv", ["dead_party", "type_A", "age_A", "type_B", "age_B", "hour", "kind", "expressway"], [
        ["歩行者", "乗用車 (自家用)", "45", "歩行者", "75", "5", "01", "False"],
        ["歩行者", "歩行者", "65", "貨物車", "30", "20", "01", "False"],
        ["歩行者", "貨物車", "45", "歩行者", "25", "19", "01", "True"],
        ["自転車", "貨物車", "45", "自転車", "75", "6", "21", "False"],
    ])
    # weekday 1 = Sunday, 7 = Saturday (Mon-Fri is 2..6).
    write(tmp_path, "hour_weekday.csv", ["group", "hour", "weekday", "accidents"], [
        ["全て", "8", "2", "3"], ["全て", "8", "1", "4"], ["全て", "17", "7", "2"], ["全て", "17", "6", "5"],
        ["自転車", "7", "3", "1"],
    ])
    write(tmp_path, "party_matrix.csv", ["party_A", "party_B", "accidents"], [
        ["乗用車 (自家用)", "自転車", "10"], ["貨物車", "自転車", "4"], ["自転車", "歩行者", "3"],
        ["二輪車", "乗用車 (自家用)", "2"], ["自転車", "相手なし・物件", "1"],
    ])
    write(tmp_path, "towns.csv", ["name", "accidents", "ped"], [["甲町", "5", "1"], ["乙町", "7", "2"]])
    write(tmp_path, "yearly.csv", ["scope", "year", "accidents", "died", "hurt"], [
        ["23区", "2019", "1000", "5", "1100"], [ward, "2019", "10", "1", "12"], [ward, "2020", "20", "0", "25"],
    ])
    write(tmp_path, "wards.csv", ["name", "share_ped", "share_bike"], [["他区", "0.9", "0.1"], [ward, "0.125", "0.5"]])
    write(tmp_path, "route_class.csv", ["year", "route_class", "accidents"], [
        ["2019", "一般道", "3"], ["2020", "一般道", "4"], ["2019", "首都高速", "1"],
    ])
    write(tmp_path, "hotspots.csv", ["top_route", "road_1", "road_2", "road_2_m", "expressway", "first_2019_2021",
                                     "second_2022_2025", "first_per_year", "second_per_year"], [
        ["一般道", "明治通り", "山手通り", "20", "0", "3", "0", "1.0", "0.0"],
        ["首都高速", "", "", "", "2", "1", "4", "0.33", "1.0"],
    ])
    write(tmp_path, "schools.csv", ["name", "young_weekday_7_8"], [["A校", "2"], ["B校", "5"]])
    (tmp_path / "school-map.json").write_text(json.dumps({"n": 7}), encoding="utf-8")
    monkeypatch.setattr(summarize, "OUT", tmp_path)
    summarize.main()
    return (tmp_path / "summary.txt").read_text(encoding="utf-8").splitlines()


def line(lines, prefix):
    found = [x for x in lines if x.startswith(prefix)]
    assert found, f"no line starting {prefix!r}"
    return found[0]


def test_deaths(lines):
    assert line(lines, "deaths accidents").startswith("deaths accidents 4; dead party {'歩行者': 3, '自転車': 1}")
    assert line(lines, "deaths hour") == "deaths hour 0-5 1; hour 19-5 3"
    assert line(lines, "dead pedestrians aged") == "dead pedestrians aged 65+ 2 of 3"


def test_hours_split_weekdays(lines):
    assert line(lines, "全て:").startswith("全て: n 14; top hours [(8, 7), (17, 7)]; weekday (Mon-Fri) n 8; "
                                          "weekday top hours [(17, 5), (8, 3)]")
    assert line(lines, "高齢の歩行者:").startswith("高齢の歩行者: n 0;")
    assert line(lines, "自転車:").startswith("自転車: n 1;")


def test_parties(lines):
    assert line(lines, "乗用車 (自家用):") == "乗用車 (自家用): as party A 10; as party B 2"
    assert line(lines, "貨物車:") == "貨物車: as party A 4; as party B 0"
    assert line(lines, "自転車: as") == "自転車: as party A 4; as party B 14"
    assert line(lines, "二輪車:") == "二輪車: as party A 2; as party B 0"
    assert line(lines, "bike as B") == "bike as B with a car or truck as A 14"


def test_towns_years_shares_school_map(lines):
    assert line(lines, "towns:").startswith("towns: accidents in towns 12; most accidents [('乙町', '7', '2'), ('甲町'")
    # Only the ward's rows of yearly.csv count, not the 23区 row.
    assert next(x for x in lines if " 7 years: accidents" in x).endswith(" 7 years: accidents 30; died 1; hurt 37")
    assert next(x for x in lines if " shares (%): " in x).endswith("share_ped 12.5; share_bike 50.0")
    assert line(lines, "school map") == "school map: young pedestrians and cyclists 7"
    assert line(lines, "party cells").startswith("party cells: 乗用車 (自家用) x 自転車 10; 貨物車 x 自転車 4")


def test_ward_specific_lines(lines):
    text = "\n".join(lines)
    if "route_class" in SOURCE:      # 7-year total by road type, summed over the yearly rows
        assert "一般道 7" in text or "'一般道': 7" in text
    if "expressway']) > 0" in SOURCE:
        assert re.search(r"with (首都高速|expressway \(4000-5499\)) accidents 1\b", text)
    if "deaths on expressways" in SOURCE:
        assert "deaths on expressways (route 4000-5499) 1" in text
    if "bike alone" in SOURCE:       # 1 of the 30 ward accidents
        assert "bike alone (A 自転車, B 相手なし・物件) 1; share of all 3.3%" in text
    if "second_per_year']) >" in SOURCE:
        assert "second half per year above first 1; below 1; both halves with accidents 1" in text
    if "in both halves" in SOURCE:
        assert "in both halves 1" in text
    if "young_weekday_7_8" in SOURCE:
        assert "schools 2; young weekday 7-8 per school min 2 max 5" in text
        # 明治通り is road_1 of one hotspot; road_2 counts only within 30 m.
        assert "明治通り 1" in text
