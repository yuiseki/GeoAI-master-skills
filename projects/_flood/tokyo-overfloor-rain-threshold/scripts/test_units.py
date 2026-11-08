"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with numpy --with pandas --with pytest pytest -q -p no:cacheprovider test_units.py"""

# reason_class and to_units of 01_units.py on a hand-made record table.
import importlib

import pandas as pd

un = importlib.import_module("01_units")

COLS = ["layer", "munic", "dis_name", "dis_date_s", "dis_date_e", "district_k", "area", "tot_bldg", "reason",
        "nro_name", "nro_60min", "nro_flag", "utf_bldg", "otf_bldg", "lon", "lat"]


def test_reason_class():
    assert un.reason_class("内水") == "naisui"
    assert un.reason_class("溢水・内水") == "issui" and un.reason_class("河川溢水") == "issui"
    assert un.reason_class("内水・その他") == "other" and un.reason_class(None) == "other"


def test_to_units_merges_rows_of_one_unit_and_reads_text_columns():
    rows = pd.DataFrame([
        # two polygons of one unit: rain = max of readable values, counts = max of leading integers
        ["a", "大田区", "台風", "1996-09-22", "1996-09-23", "k1", 1.0, 10, "内水", "田園調布", "35.5", 1, "12(2)", "3", 139.0, 35.0],
        ["a", "大田区", "台風", "1996-09-22", "1996-09-24", "k1", 1.0, 10, "内水", "田園調布", "(40)", 0, "8", "x", 139.2, 35.2],
        # second period, a city (not a ward), overflow
        ["a", "町田市", "豪雨", "1997-07-01", None, "k2", 2.0, 5, "溢水", "町田", "-", 0, "", "4", 139.4, 35.5],
        # no start date: dropped
        ["a", "北区", "豪雨", None, None, "k3", 3.0, 1, "内水", "赤羽", "50", 0, "1", "1", 139.7, 35.7],
    ], columns=COLS)
    u = un.to_units(rows).set_index("district_k")
    assert list(u.index) == ["k1", "k2"]
    k1 = u.loc["k1"]
    assert k1.rain == 35.5 and k1.utf == 12 and k1.otf == 3 and k1.nro_flag == 0 and k1.n_rows == 2
    assert k1.dis_date_e == "1996-09-24" and abs(k1.lon - 139.1) < 1e-9
    assert k1.ward and k1.cls == "naisui" and k1.period == "first" and k1.day == pd.Timestamp("1996-09-22")
    k2 = u.loc["k2"]
    assert pd.isna(k2.rain) and k2.utf == 0 and k2.otf == 4
    assert not k2.ward and k2.cls == "issui" and k2.period == "second"
