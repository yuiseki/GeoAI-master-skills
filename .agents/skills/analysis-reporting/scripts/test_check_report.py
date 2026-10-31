"""uvx --with pytest pytest test_check_report.py"""

import pytest

import subprocess
import sys
from pathlib import Path

from check_report import check, format_problems, numbers_in, sections, traceable

SIMPLE = """問い: 東京 23 区の中心部に、ヘリポートはいくつ記録されているか。
結論: OurAirports に 391 件、OpenStreetMap に 83 件。両方にあるのは 68 件 (50 m 以内)。
データ: OurAirports (2026-08-31 の凍結版)、OpenStreetMap の東京 23 区の凍結版 (2026-08-31)。範囲は 16 km × 12 km の長方形。
方法: 両方の点を 50 m 以内で 1 対 1 に照合して数えた。
"""

EVIDENCE = """$ record_overlap.py oa.parquet osm.parquet --x x --y y --radius 50
record 1: 391 rows, 391 with coordinates; record 2: 83 rows, 83 with coordinates
  all: in 1 391, in 2 83, in both 68; if independent N 476 (95% 433 to 519), seen 406; completeness 1 0.82, 2 0.17
"""


def test_sections_are_read_from_labels_and_headings():
    s = sections(SIMPLE)
    assert list(s) == ["問い", "結論", "データ", "方法"]
    md = "## 問い\n何か。\n\n## 結論\nそうだった。\n\n## データ\nX (2026-10-01)\n\n## 方法\n数えた。\n"
    assert list(sections(md)) == ["問い", "結論", "データ", "方法"]


def test_a_simple_answer_passes():
    assert check(SIMPLE, "simple", EVIDENCE) == []


def test_a_missing_section_and_a_wrong_order_are_reported():
    no_method = SIMPLE.replace("方法: 両方の点を 50 m 以内で 1 対 1 に照合して数えた。\n", "")
    assert any("方法" in p for p in check(no_method, "simple"))
    swapped = "\n".join([SIMPLE.splitlines()[i] for i in (1, 0, 2, 3)])
    assert any("order" in p for p in check(swapped, "simple"))


def test_the_question_is_one_line():
    two = SIMPLE.replace("問い: 東京 23 区の中心部に、", "問い: 東京 23 区の中心部に、\n")
    assert any("問い" in p and "one line" in p for p in check(two, "simple"))


def test_data_needs_a_version_or_a_date_or_says_it_is_unknown():
    bad = SIMPLE.replace("(2026-08-31 の凍結版)", "").replace("の凍結版 (2026-08-31)", "")
    assert any("データ" in p and "version" in p for p in check(bad, "simple"))
    ok = bad.replace("OurAirports 、", "OurAirports (版は未確認)、")
    assert not any("version" in p for p in check(ok, "simple"))


def test_a_simple_question_is_not_written_up_as_a_long_report():
    long = SIMPLE + "\n".join(f"方法の補足 {i}。" for i in range(15))
    assert any("lines" in p for p in check(long, "simple"))
    assert check(long.replace("\n方法の補足", "\n- 方法の補足"), "standard", EVIDENCE) == []


def test_a_heavy_analysis_must_say_what_was_not_checked():
    assert any("確かめていないこと" in p for p in check(SIMPLE, "full", EVIDENCE))
    full = SIMPLE + "確かめていないこと: 2 つの記録が独立かは確かめていない。\n"
    assert check(full, "full", EVIDENCE) == []


def test_numbers_by_hand():
    assert numbers_in("391 件、1,741 市区町村、0.82、82%、−3.7 分") == [
        ("391", 391.0, 0, False), ("1,741", 1741.0, 0, False), ("0.82", 0.82, 2, False), ("82%", 82.0, 0, True),
        ("−3.7", -3.7, 1, False)]


def test_conclusion_numbers_must_come_from_the_evidence_up_to_rounding():
    ev = "MAE 0.4446  completeness 1 0.8183  share 0.0008833"
    assert traceable("MAE は 0.445 で、完全性は 82%。", ev) == []
    assert traceable("学校 1 校あたり 0.00088", ev) == []
    assert traceable("MAE は 0.45 で", ev) == ["0.45"]  # 0.4446 rounds to 0.44: no double rounding
    assert traceable("MAE は 0.52 で", ev) == ["0.52"]
    assert traceable("2026-08-31 の版で 0.82", ev) == []  # dates are not results


def test_csv_rows_are_read_as_separate_numbers_and_thousands_need_groups_of_three():
    # a CSV row written without spaces: 1400 and 8.4293... are two numbers, not 14008.4293
    assert [n[1] for n in numbers_in("4 Sep-Dec,1400,8.429359966966706,-4.85")] == [4.0, 1400.0, 8.429359966966706, -4.85]
    assert traceable("MAE は 8.429", "hgb_nb,4,4 Sep-Dec,1400,8.429359966966706") == []
    # thousands separators still read as one number
    assert [n[1] for n in numbers_in("1,168,211 セル、12,345 件")] == [1168211.0, 12345.0]


def test_a_csv_row_of_three_digit_values_in_the_evidence_is_also_read_value_by_value():
    # "285,245,13" looks like the thousands-grouped 285,245; in the evidence each value must also count
    ev = "ward,both,model_only\n品川区,285,245,13"
    assert traceable("品川区は両方 285、予測モデルだけ 245", ev) == []
    assert traceable("285,245 件", ev) == []  # the grouped reading stays possible
    # in the conclusion, a grouped number is still one number
    assert traceable("1,168,211 セル", "1168211") == []
    assert traceable("1,168 セル", "1,168211") == ["1,168"]


def test_a_word_ending_in_table_or_figure_is_not_a_reference():
    ev = "auc 0.6149 n 835"
    # 箇所表 (a list of places) and 地図 (a map) are words, not "表 N" or "図 N"
    assert traceable("箇所表 0.61、835 か所", ev) == []
    assert traceable("箇所表 0.72", ev) == ["0.72"]
    assert traceable("地図 9 枚", ev) == ["9"]
    # a reference is followed by a whole number, not a decimal
    assert traceable("図 0.61 の値", ev) == []
    assert traceable("図 4 と表 2 のとおり 0.61", ev) == []


def test_figure_and_table_references_and_row_numbers_are_not_results():
    # a figure-led conclusion: the points table numbers its rows and links to "### 図 N: ..." headings
    md = """## 問い
件数は減ったか。

## 結論

### 要点

| # | 要点 | 数字 | 図 |
|---:|---|---|---|
| 3 | 減った | 0.445 | [図 4](#図-4-件数の推移)、[表 2](#表-2-上位)、[別の報告](../grid-100m/report.md) |

### 図 4: 件数の推移

表 2 と同じ向き。

## データ
X (2026-10-01)

## 方法
数えた。
"""
    assert check(md, "standard", "MAE 0.4446") == []
    assert any("7" in p for p in check(md.replace("0.445", "0.445、7 件"), "standard", "MAE 0.4446"))


def test_unknown_level_stops():
    with pytest.raises(ValueError):
        check(SIMPLE, "long")


def test_unit_words_and_km_settings_are_not_results():
    ev = "$ accessibility.py --catchment 1000\ndemand-weighted mean 0.000883293"
    assert traceable("子ども 1 人あたり 0.000883、1 km 以内の学校で", ev) == []
    assert traceable("学校 1 校に子ども約 1,130 人", ev) == ["1,130"]  # divided by hand: not in the outputs
    assert traceable("2 km 以内で", ev) == ["2"]


def test_the_report_is_a_markdown_file():
    # asked only to "visualise the burger shops", an agent wrote its report as an HTML page
    assert format_problems("projects/x/report.md", SIMPLE) == []
    assert format_problems("projects/x/report.html", SIMPLE)
    assert format_problems("projects/x/report.ipynb", SIMPLE)


def test_html_page_markup_in_the_report_is_refused():
    page = "<!DOCTYPE html>\n<html><body>\n" + SIMPLE + "<script src=\"map.js\"></script></body></html>\n"
    assert any("HTML" in x for x in format_problems("report.md", page))
    assert format_problems("report.md", SIMPLE + "\n![分布](outputs/map.png)\n") == []


def test_github_markdown_table_math_mermaid_and_png_are_allowed():
    report = """## 問い
2 地域の到達率はどう違うか。

## 結論
到達率は甲が 80%、乙が 60%。

## データ
調査票 (2026-10-01)、2 地域。

## 方法
到達率は到達件数を対象件数で割った。
| 地域 | 到達率 |
|---|---:|
| 甲 | 80% |
| 乙 | 60% |
```math
r = n_{reached} / n_{eligible}
```
```mermaid
flowchart LR
  A[調査票] --> B[到達率]
```
![地域別の到達率](outputs/rate.png)
"""
    assert format_problems("report.md", report) == []
    assert check(report, "standard", "80% 60%") == []


def test_fenced_content_counts_toward_simple_line_limit():
    report = SIMPLE + "```mermaid\nflowchart LR\n  A --> B\n  B --> C\n  C --> D\n```\n"
    assert any("lines" in p for p in check(report, "simple", EVIDENCE))


def test_html_page_markup_remains_forbidden_even_in_fenced_content():
    report = SIMPLE + "```html\n<div>interactive map</div>\n```\n"
    assert any("HTML" in p for p in format_problems("report.md", report))


def test_command_line_stops_on_an_html_report(tmp_path):
    f = tmp_path / "report.html"
    f.write_text(SIMPLE, encoding="utf-8")
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("check_report.py")), str(f), "--level", "simple"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "Markdown" in r.stdout


def test_a_value_on_the_rounding_tie_matches_either_way():
    # towns.csv held 5.665 and the report wrote 5.66: a tie at the report's precision may go either way
    assert traceable("5.66 件", "5.665") == []
    assert traceable("5.67 件", "5.665") == []
    assert traceable("5.66 件", "5.6649") == []
    assert traceable("5.67 件", "5.664") == ["5.67"]
    assert traceable("5.65 件", "5.665") == ["5.65"]


def test_a_year_is_a_date_not_a_value():
    # "1981〜2000年と2006〜2025年で" names periods; a count such as 2000 件 is still a value
    assert numbers_in("1981〜2000年と2006〜2025年で 0.997。2011 年から 2015年まで") == [("0.997", 0.997, 3, False)]
    assert numbers_in("2000 件") == [("2000", 2000.0, 0, False)]
    assert numbers_in("2,000年") == [("2,000", 2000.0, 0, False)]


def test_a_number_in_exponent_notation_is_one_number():
    # common_pixel_summary.json wrote 2.342224132867443e-06; the report says 0.0000023
    assert traceable("最大0.0000023 Mg/ha", '{"max_abs_delta": 2.342224132867443e-06}') == []
    assert traceable("最大0.0000024 Mg/ha", '{"max_abs_delta": 2.342224132867443e-06}') == ["0.0000024"]
    assert traceable("1.5", '{"x": 1.5E+00}') == []


def test_a_hash_is_not_read_as_exponent_notation():
    # jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135: e13135 is part of the hash, not an exponent
    tokens = [t for t, *_ in numbers_in("版 e6c87b1d7095c17422147962185071a986e13135")]
    assert not any("e" in t for t in tokens), tokens


def test_a_per_mille_matches_the_fraction():
    # b5_diagnostics.json holds 0.0242 and the report writes 24.2‰
    assert traceable("Q1 の陽性の割合 24.2‰", '{"q1": 0.0242}') == []
    assert traceable("Q1 の陽性の割合 24.2‰", '{"q1": 0.242}') == ["24.2‰"]


def test_a_list_of_figure_numbers_is_a_reference():
    # "図 6、7、9、11、12 は各プロジェクトの地図" and "図 6〜12" number figures, not values
    assert traceable("図 6、7、9、11、12 は地図。図 6〜12 を見る。", "") == []
    assert traceable("図 6 は 0.552", "") == ["0.552"]


def test_a_month_is_a_date_not_a_value():
    # "4 週先の 9〜12 月の MAE は 8.429" and "10 月以降" name months
    assert [t for t, *_ in numbers_in("4 週先の 9〜12 月の MAE は 8.429。10 月以降")] == ["4", "8.429"]
    assert [t for t, *_ in numbers_in("13 月")] == ["13"]
