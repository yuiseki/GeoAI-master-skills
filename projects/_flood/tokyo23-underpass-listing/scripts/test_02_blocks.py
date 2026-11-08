"""uvx --python 3.12 --with numpy --with pandas --with pytest pytest -q -p no:cacheprovider test_02_blocks.py"""

# blocks_for and b4 of 02_blocks.py on a hand-made table of underpass units.
import importlib

import pandas as pd
import pytest

bk = importlib.import_module("02_blocks")


def units():
    # 10 units in one 2 km block (so every block resample is the table itself and the intervals collapse).
    # Listed (d_list <= 100): units 0-4, one of them flooded; unlisted: 5-9, three flooded.
    return pd.DataFrame({
        "x": [10.0] * 10, "y": [20.0] * 10,
        "d_list": [0, 20, 50, 80, 100, 101, 150, 300, 900, 1000],
        "d_kansui": [0, 500, 500, 500, 50, 500, 500, 500, 500, 99],
        "flood": [1, 0, 0, 0, 0, 1, 1, 1, 0, 0],
        "flood30": [0] * 10,
        "len_m": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        "road_class": ["primary"] * 5 + ["residential"] * 5,
        "form": ["under"] * 10,
    })


def test_blocks_for_main_numbers_and_verdicts():
    r = bk.blocks_for(units())
    assert (r["units"], r["listed"], r["flood"], r["flood_listed"], r["flood_unlisted"], r["blocks"]) == (10, 5, 4, 1, 3, 1)
    assert r["B1_share_listed"] == 0.5 and r["B1_ci"] == [0.5, 0.5] and r["B1_share_listed_pct"] == 50.0
    assert (r["B2_flood_share_listed"], r["B2_flood_share_unlisted"], r["B2_diff"]) == (0.2, 0.6, -0.4)
    assert r["B3_unlisted_share_of_flood"] == 0.75 and r["B3_ci"] == [0.75, 0.75]
    assert r["bootstrap_used"] == {"B2": 2000, "B3": 2000}
    # C1: share listed under 0.5? the interval sits at 0.5 -> rejected; C2: difference above 0? -> rejected;
    # C3: unlisted share of the flooded above 0.2 -> supported
    assert r["verdict"] == {"C1": "退ける", "C2": "退ける", "C3": "支持"}


def test_blocks_for_distance():
    r = bk.blocks_for(units(), d=50)
    assert r["listed"] == 3 and r["flood_listed"] == 1 and r["B2_flood_share_unlisted"] == round(3 / 7, 3)


def test_blocks_for_with_no_flooded_unit():
    r = bk.blocks_for(units(), flood="flood30")
    assert r["flood"] == 0 and r["B3_unlisted_share_of_flood"] is None
    assert "B3_unlisted_share_of_flood_pct" not in r
    assert r["B3_ci"] == [None, None] and r["verdict"]["C3"].startswith("not judged")


def test_b4_tables_by_kind():
    t = bk.b4(units()).set_index(["by", "value"])
    assert t.loc[("road_class", "primary"), "listed"] == 5 and t.loc[("road_class", "residential"), "listed"] == 0
    assert t.loc[("road_class", "primary"), "kansui"] == 2 and t.loc[("road_class", "residential"), "kansui"] == 1
    assert t.loc[("form", "under"), "units"] == 10 and t.loc[("form", "under"), "flood"] == 4
    # thirds of len_m: 10-40, 50-70, 80-100
    assert t.loc[("length", "short"), "units"] == 4 and t.loc[("length", "middle"), "units"] == 3
    assert t.loc[("length", "long"), "len_m_median"] == 90.0
