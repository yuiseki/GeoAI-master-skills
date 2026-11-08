"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with pytest pytest -q test_kansui_labels.py"""

# Tests for kansui_labels.py: distances from underpasses to 冠水想定箇所 points, and the signs read from the
# 箇所表 PDF text. The three pinned Hugging Face paths (UP, KP, PDF) are pointed at small parquet files built
# in tmp_path, so nothing goes to the network. The DuckDB spatial extension must already be installed locally.
#
# Distances: one degree of latitude is about 111.2 km on the sphere, so 0.0002 deg is 22 m, 0.0005 deg 56 m,
# 0.0008 deg 89 m, 0.002 deg 222 m and 0.005 deg 556 m.

import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

SRC = Path(__file__).parent / "kansui_labels.py"

KANSUI = [  # fid, pref, lon, lat
    (1, "東京都", 139.70, 35.70),
    (2, "東京都", 139.80, 35.70),
    (3, "大阪府", 135.50, 34.70),
    (4, "大阪府", 135.60, 34.70),
    (5, "東京都", 139.90, 35.90),
    (6, "東京都", 139.95, 35.95),
]
UNDERPASSES = [  # id, pref, lon, lat
    ("u1", "東京都", 139.70, 35.70),      # on point 1: 0 m
    ("u2", "東京都", 139.80, 35.7002),    # 22 m from point 2
    ("u3", "大阪府", 135.50, 34.7008),    # 89 m from point 3
    ("u4", "大阪府", 135.60, 34.702),     # 222 m from point 4
    ("u5", "東京都", 139.70, 35.705),     # 556 m from point 1
    ("u6", "京都府", 135.50, 34.7005),    # no KML in 京都府, but 56 m from point 3 of 大阪府
    ("u7", "北海道", 141.00, 43.00),      # no point within 0.05 deg
    ("u8", "北海道", 141.20, 43.10),
]
POINT_PDF = [  # fid, pdf_match, pdf_key
    (1, "pdf_unique", "A"),
    (2, "pdf_unique", "B"),
    (3, "pdf_unique", "C"),
    (4, "pdf_shared", "D"),   # a shared PDF: its signs are not counted
    (5, "pdf_unique", "E"),   # layout_unknown: not counted
    (6, "pdf_unique", "F"),   # no record for F: parse_status is null, not counted
]
HOKURIKU = {"1m以上の冠水の有無": "有", "排水ポンプの有無": "有", "注意喚起方法": "電光表示板", "情報入手方法": "水位計"}
RECORDS = [  # pdf_key, layout, parse_status, remarks, extra_cells
    ("A", "kanto", "ok", "H30年7月の豪雨で冠水", None),
    ("B", "kanto", "ok", "冠水実績なし。排水ポンプ設置", None),
    ("C", "hokuriku", "ok", None, json.dumps(HOKURIKU, ensure_ascii=False)),
    ("D", "kanto", "ok", "台風19号で冠水", None),
    ("E", "kanto", "layout_unknown", "冠水実績あり", None),
]


def load():
    spec = importlib.util.spec_from_file_location("kansui_labels", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_inputs(d: Path, records=RECORDS, point_pdf=POINT_PDF):
    c = duckdb.connect()
    c.execute("create table u(id varchar, pref varchar, lon double, lat double)")
    c.executemany("insert into u values (?, ?, ?, ?)", UNDERPASSES)
    c.execute("create table k(fid int, pref varchar, lon double, lat double)")
    c.executemany("insert into k values (?, ?, ?, ?)", KANSUI)
    c.execute("create table pp(fid int, pdf_match varchar, pdf_key varchar)")
    c.executemany("insert into pp values (?, ?, ?)", point_pdf)
    c.execute("create table r(pdf_key varchar, layout varchar, parse_status varchar, remarks varchar, extra_cells varchar)")
    c.executemany("insert into r values (?, ?, ?, ?, ?)", records)
    (d / "pdf").mkdir()
    c.execute(f"copy u to '{d}/national.parquet' (format parquet)")
    c.execute(f"copy k to '{d}/kansui_points.parquet' (format parquet)")
    c.execute(f"copy pp to '{d}/pdf/point_pdf.parquet' (format parquet)")
    c.execute(f"copy r to '{d}/pdf/pdf_records.parquet' (format parquet)")


def run(tmp_path, monkeypatch, capsys, **inputs):
    write_inputs(tmp_path, **inputs)
    mod = load()
    monkeypatch.setattr(mod, "UP", str(tmp_path / "national.parquet"))
    monkeypatch.setattr(mod, "KP", str(tmp_path / "kansui_points.parquet"))
    monkeypatch.setattr(mod, "PDF", str(tmp_path / "pdf"))
    mod.main()
    return json.loads(capsys.readouterr().out)


@pytest.fixture
def out(tmp_path, monkeypatch, capsys):
    return run(tmp_path, monkeypatch, capsys)


def test_counts_and_prefectures_without_a_kml(out):
    assert out["underpasses"] == 8
    assert out["kansui_points"] == 6
    assert out["underpasses_in_kml_prefs"] == 5
    assert out["prefs_without_kml"] == [["北海道", 2], ["京都府", 1]]


def test_near_counts_are_cumulative_by_great_circle_distance(out):
    assert out["near"] == {"10m": 1, "30m": 2, "100m": 3, "300m": 4}


def test_an_underpass_in_a_prefecture_without_kml_is_counted_apart(out):
    assert out["near_outside_kml_prefs_100m"] == 1


def test_points_with_an_underpass_within_30m(out):
    assert out["kansui_with_underpass_30m"] == 2


def test_pdf_match_tally(out):
    assert out["pdf_match"] == {"pdf_unique": 5, "pdf_shared": 1}


def test_signs_are_counted_only_on_readable_own_pdfs(out):
    # readable and own: points 1, 2, 3
    assert out["readable_own_pdf"] == 3
    # 1: a year next to 冠水; 2: says none, names a pump; 3: Hokuriku cells for deep, pump, warning and sensor
    assert out["signs"] == {"record": 1, "pump": 2, "sensor": 1, "warning": 1, "deep": 1}
    assert out["said_none"] == 1
    assert out["any_record_or_deep"] == 2
    assert sorted(map(tuple, out["record_or_deep_by_pref"])) == [("大阪府", 1, 1), ("東京都", 1, 2)]


def test_underpasses_within_30m_take_the_signs_of_their_nearest_point(out):
    # u1 -> point 1 (record), u2 -> point 2 (pump)
    assert out["underpass_30m_readable"] == 2
    assert out["underpass_30m_signs"] == {"record": 1, "pump": 1, "sensor": 0, "warning": 0, "deep": 0}
    assert out["underpass_30m_record_or_deep"] == 1


def test_record_examples_are_the_free_text(out):
    assert out["record_examples"] == ["H30年7月の豪雨で冠水"]


@pytest.mark.parametrize("text, record", [
    ("H30年7月の豪雨で冠水", True),
    ("令和元年10月 冠水", True),
    ("Ｒ２．７ 冠水", True),
    ("台風第19号により冠水", True),
    ("冠水 2019年", True),
    ("冠水履歴あり", True),
    ("冠水実績なし", False),
    ("冠水実績無", False),
    ("冠水実績はない", False),
    ("過去に冠水実績あり、現在は冠水解消", False),
    ("道路冠水の恐れ", False),
    ("", False),
])
def test_the_record_sign(text, record):
    mod = load()
    got = duckdb.execute(f"select {mod.SIGNS['record']} from (select ? as txt)", [text]).fetchall()[0][0]
    assert got is record


def test_a_missing_pdf_parquet_fails_loudly(tmp_path, monkeypatch, capsys):
    write_inputs(tmp_path)
    (tmp_path / "pdf" / "pdf_records.parquet").unlink()
    mod = load()
    monkeypatch.setattr(mod, "UP", str(tmp_path / "national.parquet"))
    monkeypatch.setattr(mod, "KP", str(tmp_path / "kansui_points.parquet"))
    monkeypatch.setattr(mod, "PDF", str(tmp_path / "pdf"))
    with pytest.raises(duckdb.Error, match="pdf_records"):
        mod.main()
    assert capsys.readouterr().out == ""


def test_a_text_saying_there_is_no_pump_is_not_a_pump_sign(tmp_path, monkeypatch, capsys):
    records = [r if r[0] != "A" else ("A", "kanto", "ok", "排水ポンプなし", None) for r in RECORDS]
    out = run(tmp_path, monkeypatch, capsys, records=records)
    assert out["signs"]["pump"] == 2   # points 2 and 3 only
