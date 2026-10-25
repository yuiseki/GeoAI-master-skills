"""uvx --with pytest pytest scripts/test_check_paper.py"""

from check_paper import check_paper


PAPER = """# 観測のない地域の予測

## 要旨
地域を伏せた予測を評価した。既存の結果だけを報告する。

## 1. はじめに
研究上の問いを置く。

## 2. データ
版を固定した観測を用いる。

## 3. 方法
```math
r = a / b
```
```mermaid
flowchart LR
  A[観測] --> B[評価]
```

## 4. 結果
![図1: 評価結果](outputs/result.png)

## 5. 頑健性と限界
未検証の条件を示す。

## 6. 考察
別の説明を記す。関連研究は十分に調査していない。

## 7. 結論
結果から言える範囲を示す。
"""


def write_paper(tmp_path, text=PAPER, name="paper.md"):
    paper = tmp_path / name
    (tmp_path / "outputs").mkdir(exist_ok=True)
    (tmp_path / "outputs" / "result.png").write_bytes(b"PNG")
    paper.write_text(text, encoding="utf-8")
    return paper


def test_japanese_paper_with_math_mermaid_and_local_png_passes(tmp_path):
    assert check_paper(write_paper(tmp_path)) == []


def test_requires_markdown_title_abstract_and_core_sections(tmp_path):
    paper = write_paper(tmp_path, PAPER.replace("# 観測のない地域の予測", "観測のない地域の予測")
                        .replace("## 要旨", "## 概要")
                        .replace("## 2. データ", "## 対象")
                        .replace("## 3. 方法", "## 手順")
                        .replace("## 4. 結果", "## 発見")
                        .replace("## 5. 頑健性と限界", "## 付録"), name="paper.txt")
    problems = check_paper(paper)
    assert any("Markdown" in p for p in problems)
    for label in ("Title", "Abstract", "Data", "Methods", "Results", "Limitations"):
        assert any(label in p for p in problems)


def test_missing_png_is_reported(tmp_path):
    paper = write_paper(tmp_path, PAPER.replace("outputs/result.png", "outputs/missing.png"))
    assert any("missing.png" in p for p in check_paper(paper))


def test_unclosed_mermaid_or_math_fence_is_reported(tmp_path):
    paper = write_paper(tmp_path, PAPER.replace("  A[観測] --> B[評価]\n```", "  A[観測] --> B[評価]"))
    assert any("fence" in p for p in check_paper(paper))


def test_html_page_markup_is_rejected(tmp_path):
    paper = write_paper(tmp_path, PAPER + "<div>本文</div>\n")
    assert any("HTML" in p for p in check_paper(paper))


def test_headings_inside_a_fence_do_not_satisfy_structure(tmp_path):
    paper = write_paper(tmp_path, PAPER.replace("## 2. データ\n版を固定した観測を用いる。", "```text\n## 2. データ\n```"))
    assert any("Data" in p for p in check_paper(paper))
