"""uvx --python 3.12 --with openpyxl --with pytest pytest -q -p no:cacheprovider test_parse_lists.py"""

# The three list readers of parse_lists.py; pdftotext is replaced by fixed text, the Excel sheet is built in tmp_path.
import openpyxl
import pytest

import parse_lists as pl


def test_kagawa_rows_and_numbering(monkeypatch):
    monkeypatch.setattr(pl, "text", lambda path: "  防災重点ため池一覧\n  1  大池  高松市香川町 1-2 \n 2 新池   高松市 3\n")
    rows = pl.kagawa("k.pdf", "高松市")
    assert [(r["no"], r["name"], r["address"]) for r in rows] == [(1, "大池", "高松市香川町 1-2"), (2, "新池", "高松市 3")]
    assert rows[0]["box"] == "kagawa" and rows[0]["municipality"] == "高松市" and rows[0]["storage_thousand_m3"] == ""


def test_kagawa_refuses_a_gap_in_the_numbers(monkeypatch):
    monkeypatch.setattr(pl, "text", lambda path: " 1 大池 高松市\n 3 新池 高松市\n")
    with pytest.raises(AssertionError):
        pl.kagawa("k.pdf", "高松市")


def test_hiroshima_columns_and_missing_names(monkeypatch):
    lines = [
        "340000001  大池   おおいけ   広島県 福山市  駅家町 1   12.5  3.0  45.6",
        "340000002  ふりがなだけ   広島県 尾道市  美ノ郷町   8.0  1.0  10.0",
        "340000003  中池   なかいけ   広島県 三原市  本郷 2   5.0  1.0  2.0",     # not in the box
        "340000004  小池   こいけ   広島県 府中市  上下町",                        # numbers missing
        "12345  関係ない行",
    ]
    monkeypatch.setattr(pl, "text", lambda path: "\n".join(lines))
    rows = pl.hiroshima("h.pdf")
    assert [r["no"] for r in rows] == ["340000001", "340000002", "340000004"]
    assert rows[0]["name"] == "大池" and rows[0]["address"] == "駅家町 1"
    assert (rows[0]["dam_height_m"], rows[0]["storage_thousand_m3"]) == ("12.5", "45.6")
    assert rows[1]["name"] == "" and rows[1]["municipality"] == "尾道市"     # one part: the name did not come out
    assert rows[2]["dam_height_m"] == "" and rows[2]["storage_thousand_m3"] == ""
    assert len(pl.hiroshima("h.pdf", munis=None)) == 4


def test_hyogo_keeps_rows_with_a_bousai_date_in_the_box(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(5):
        ws.append(["header"])
    ws.append(["A1", None, "大池", "淡路市", "岩屋 1", None, None, "2021-04-01"])
    ws.append(["A2", None, None, "洲本市五色町", "鮎原", None, None, "2021-04-01"])
    ws.append(["A3", None, "小池", "淡路市", "岩屋 2", None, None, None])        # not designated
    ws.append(["A4", None, "中池", "南あわじ市", "市 3", None, None, "2021-04-01"])  # outside the box
    wb.save(tmp_path / "hyogo.xlsx")
    rows = pl.hyogo(tmp_path / "hyogo.xlsx")
    assert [(r["no"], r["name"], r["municipality"]) for r in rows] == [("A1", "大池", "淡路市"), ("A2", "", "洲本市五色町")]
    assert len(pl.hyogo(tmp_path / "hyogo.xlsx", munis=None)) == 3
