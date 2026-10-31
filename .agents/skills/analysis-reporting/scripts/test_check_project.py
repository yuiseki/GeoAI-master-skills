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
