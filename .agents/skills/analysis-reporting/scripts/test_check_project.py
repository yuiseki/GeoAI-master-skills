"""uvx --with pytest pytest test_check_project.py"""

import subprocess
import sys
from pathlib import Path

from check_project import check_project, dead_links, evidence_for, not_utf8

HERE = Path(__file__).parent

REPORT = """# 区の事故

## 問い

区の事故はどこで起きているか。

## 結論

事故は 4,232 件で、自転車が関わる事故は 27.3%。上位は [表](outputs/hotspots.csv) にある。

![図](outputs/map.png)

## データ

- 事故: npa-traffic-accidents 版 389500a

## 方法

半径 30 m の円で数えた。

## 確かめていないこと

交通量で割っていない。
"""


def make_project(root: Path, report: str = REPORT, readme: bool = True) -> Path:
    project = root / "projects" / "ward-accidents"
    (project / "outputs").mkdir(parents=True)
    (project / "report.md").write_text(report, encoding="utf-8")
    if readme:
        (project / "README.md").write_text("# 区の事故\n\n再実行: `python scripts/analyze.py`\n", encoding="utf-8")
    (project / "outputs" / "summary.json").write_text('{"accidents": 4232, "share_bike": 0.2727}', encoding="utf-8")
    (project / "outputs" / "hotspots.csv").write_text("rank,accidents\n1,32\n", encoding="utf-8")
    (project / "outputs" / "map.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return project


def test_a_complete_project_passes(tmp_path):
    assert check_project(make_project(tmp_path)) == []


def test_a_number_the_outputs_do_not_hold_is_reported(tmp_path):
    # the Chiyoda report wrote 23.3% where the outputs held 0.2727
    project = make_project(tmp_path, REPORT.replace("27.3%", "23.3%"))
    assert check_project(project) == ["report.md: 結論: 23.3% does not appear in the evidence"]


def test_missing_sections_are_reported(tmp_path):
    report = REPORT.split("## データ")[0]
    problems = check_project(make_project(tmp_path, report))
    assert "report.md: データ: missing or empty" in problems
    assert "report.md: 方法: missing or empty" in problems
    assert "report.md: 確かめていないこと: a full report says what was not checked" in problems


def test_a_link_to_a_file_that_does_not_exist_is_reported(tmp_path):
    # the Chiyoda report linked reports/municipality.md, which was never written
    report = REPORT.replace("## データ", "詳しくは [区の担当向け](reports/municipality.md#要点)。\n\n## データ")
    assert dead_links(make_project(tmp_path, report) / "report.md") == ["reports/municipality.md"]
    assert check_project(make_project(tmp_path / "b", report)) == [
        "report.md: links to reports/municipality.md, which does not exist"]


def test_links_that_are_not_files_are_not_checked(tmp_path):
    report = REPORT.replace("## データ", "[上へ](#問い)、[警察庁](https://www.npa.go.jp/)、<mailto:a@example.com>\n\n## データ")
    assert dead_links(make_project(tmp_path, report) / "report.md") == []


def test_a_link_inside_a_code_block_is_not_checked(tmp_path):
    report = REPORT.replace("## データ", "```\n[例](missing.md)\n```\n\n## データ")
    assert dead_links(make_project(tmp_path, report) / "report.md") == []


def test_an_output_that_is_not_utf8_is_reported_without_crashing(tmp_path):
    # the Chiyoda outputs had one CSV written in cp932 by a Windows default
    project = make_project(tmp_path)
    (project / "outputs" / "towns.csv").write_bytes("町丁,件数\n神田,69\n".encode("cp932"))
    assert not_utf8(project) == ["outputs/towns.csv"]
    assert check_project(project) == ["outputs/towns.csv is not UTF-8: write text outputs with encoding='utf-8'"]


def test_a_missing_readme_is_reported(tmp_path):
    assert check_project(make_project(tmp_path, readme=False)) == [
        "README.md is missing: say what the project is and how to run it again"]


def test_a_project_without_a_report_is_reported(tmp_path):
    project = make_project(tmp_path)
    (project / "report.md").unlink()
    assert check_project(project) == ["report.md is missing"]


def test_a_linked_project_lends_its_outputs_as_evidence(tmp_path):
    # a synthesis quotes the numbers of the projects it links to
    other = tmp_path / "projects" / "grid"
    (other / "outputs").mkdir(parents=True)
    (other / "outputs" / "scores.json").write_text('{"capture": 0.552}', encoding="utf-8")
    (other / "report.md").write_text("# grid\n", encoding="utf-8")
    report = REPORT.replace("27.3%", "27.3%、[格子](../grid/report.md) は 0.552")
    project = make_project(tmp_path, report)
    assert "0.552" in evidence_for(project, report)
    assert check_project(project) == []


def test_the_command_line_names_each_project_and_exits_1(tmp_path):
    good = make_project(tmp_path / "a")
    bad = make_project(tmp_path / "b", REPORT.replace("27.3%", "23.3%"))
    run = subprocess.run([sys.executable, str(HERE / "check_project.py"), str(good), str(bad)],
                         capture_output=True, text=True)
    assert run.returncode == 1
    assert f"{good}: ok" in run.stdout
    assert f"{bad}: report.md: 結論: 23.3% does not appear in the evidence" in run.stdout


KEY_TABLE = """# 区の事故

## 問い

区の事故はどこで起きているか。

## 結論

| # | 要点 | 数字 |
|---:|---|---|
| 1 | 件数は戻りつつある | 2024 年は 1,837 件 ([yearly.csv](outputs/yearly.csv)) |
| 2 | 自転車が多い | 27.3% ([wards.csv](outputs/wards.csv)) |

## データ

- 事故: npa-traffic-accidents 版 389500a

## 方法

半径 30 m の円で数えた。

## 確かめていないこと

交通量で割っていない。
"""


def make_cited(root: Path, report: str = KEY_TABLE) -> Path:
    project = root / "projects" / "cited"
    (project / "outputs").mkdir(parents=True)
    (project / "report.md").write_text(report, encoding="utf-8")
    (project / "README.md").write_text("# cited\n", encoding="utf-8")
    (project / "outputs" / "yearly.csv").write_text("year,accidents\n2024,1837\n", encoding="utf-8")
    (project / "outputs" / "wards.csv").write_text("name,share_bike\n世田谷区,0.2727\n", encoding="utf-8")
    # a big table elsewhere in the outputs that happens to hold 1732
    (project / "outputs" / "hour_weekday.csv").write_text("hour,accidents\n8,1732\n", encoding="utf-8")
    return project


def test_key_rows_that_cite_their_outputs_pass(tmp_path):
    assert check_project(make_cited(tmp_path)) == []


def test_a_cited_row_is_traced_only_in_the_files_it_cites(tmp_path):
    # the Setagaya reader report wrote 1,732 for 2024; the outputs held 1732 only in an unrelated table
    project = make_cited(tmp_path, KEY_TABLE.replace("1,837", "1,732"))
    assert check_project(project) == ["report.md: 1,732 is not in outputs/yearly.csv"]


def test_a_key_row_without_a_cited_output_is_reported(tmp_path):
    project = make_cited(tmp_path, KEY_TABLE.replace(" ([wards.csv](outputs/wards.csv))", ""))
    assert check_project(project) == ["report.md: 要点 row 2 cites no file in outputs/: link the output each number comes from"]


def test_digits_in_a_cited_file_name_are_not_traced(tmp_path):
    project = make_cited(tmp_path)
    (project / "outputs" / "b1_main.json").write_text('{"capture": 0.552}', encoding="utf-8")
    report = KEY_TABLE.replace("27.3% ([wards.csv](outputs/wards.csv))", "0.552 ([b1_main.json](outputs/b1_main.json))")
    assert check_project(make_cited(tmp_path / "b", report)) != []  # b1_main.json is missing in the second project
    (project / "report.md").write_text(report, encoding="utf-8")
    assert check_project(project) == []


def test_numbers_in_reader_reports_are_traced(tmp_path):
    project = make_cited(tmp_path)
    (project / "reports").mkdir()
    (project / "reports" / "municipality.md").write_text(
        "# 区の担当向け\n\n2024 年は 1,837 件 ([yearly.csv](../outputs/yearly.csv))。自転車は 27.3%。\n", encoding="utf-8")
    assert check_project(project) == []
    (project / "reports" / "municipality.md").write_text(
        "# 区の担当向け\n\n2024 年は 1,732 件 ([yearly.csv](../outputs/yearly.csv))。自転車は 23.3%。\n", encoding="utf-8")
    assert check_project(project) == ["reports/municipality.md: 1,732 is not in outputs/yearly.csv",
                                      "reports/municipality.md: 23.3% does not appear in the evidence"]


def test_a_small_integer_in_a_cited_row_may_come_from_any_output(tmp_path):
    # "7 年で" counts the years of the study, not a value of the cited file; small integers match by chance anyway
    project = make_cited(tmp_path, KEY_TABLE.replace("2024 年は 1,837 件", "7 年のうち 2024 年は 1,837 件"))
    (project / "outputs" / "summary.txt").write_text("years 7\n", encoding="utf-8")
    assert check_project(project) == []
    (project / "outputs" / "summary.txt").write_text("years 9\n", encoding="utf-8")
    assert check_project(project) == ["report.md: 7 is not in outputs/yearly.csv"]


def test_a_setting_stated_in_the_method_may_appear_in_a_cited_row(tmp_path):
    # "100m配分" names a method; the method section says 100 m, the cited file has no 100 in it
    report = KEY_TABLE.replace("2024 年は 1,837 件", "100m配分で 2024 年は 1,837 件").replace(
        "半径 30 m の円で数えた。", "半径 30 m の円で数え、人口は 100 m の格子で配った。")
    assert check_project(make_cited(tmp_path, report)) == []
    assert check_project(make_cited(tmp_path / "b", report.replace("100 m の格子", "細かい格子"))) == [
        "report.md: 100 is not in outputs/yearly.csv"]


def test_a_number_in_a_cited_file_name_counts_as_evidence(tmp_path):
    # "Δ 上位20の区別は" cites top20_delta.csv, whose name says it holds the top 20
    project = make_cited(tmp_path)
    (project / "outputs" / "top20_delta.csv").write_text("mesh,ward\n1,千代田区\n", encoding="utf-8")
    report = KEY_TABLE.replace("27.3% ([wards.csv](outputs/wards.csv))", "上位20 ([top20_delta.csv](outputs/top20_delta.csv))")
    (project / "report.md").write_text(report, encoding="utf-8")
    assert check_project(project) == []
