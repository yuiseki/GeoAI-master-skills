"""uvx --with pytest pytest test_calibrate_checks.py"""

import random

from calibrate_checks import MUTATIONS, add_claim, break_link, conclusion_span, drop_failure_row, drop_section, \
    perturb_number, swap_unit

REPORT = """# 例

## 問い

区の事故はどこで起きているか。

## 結論

事故は 4,232 件で、自転車が関わる事故は 27.3%。平均の距離は 1.85 km ([表](outputs/summary.csv))。

## データ

- 事故 (2026-08-31 の版)

## 方法

半径 30 m の円で数えた。

## 失敗の型

| ID | 判定 | 根拠 |
|---|---|---|
| F1 | 確かめた | 照合した |
| F2 | 当てはまらない | 比べていない |

## 確かめていないこと

交通量で割っていない。
"""


def test_conclusion_span_covers_only_the_conclusion():
    a, b = conclusion_span(REPORT)
    block = REPORT[a:b]
    assert "4,232" in block and "半径" not in block and "区の事故は" not in block


def test_perturb_number_changes_one_number_in_the_conclusion_only():
    rng = random.Random(0)
    seen = set()
    for _ in range(30):
        out, note = perturb_number(REPORT, rng)
        assert out != REPORT and "30 m" in out and "2026-08-31" in out
        a, b = conclusion_span(REPORT)
        assert out[:a] == REPORT[:a]
        seen.add(note.split(" -> ")[0])
    assert seen == {"4,232", "27.3%", "1.85"}          # every number can be chosen; dates and the link are not


def test_perturbed_numbers_keep_their_format_but_not_their_value():
    rng = random.Random(1)
    for _ in range(30):
        _, note = perturb_number(REPORT, rng)
        old, new = note.split(" -> ")
        new = new.rsplit(" (", 1)[0]
        assert old != new
        assert ("," in old) == ("," in new) and old.endswith("%") == new.endswith("%")
        assert ("." in old) == ("." in new)


def test_structural_mutations():
    assert "## データ" not in drop_section(REPORT, "データ")[0]
    out, note = break_link(REPORT)
    assert "outputs/summary.csv" not in out and "missing" in out
    out, note = drop_failure_row(REPORT, random.Random(0))
    assert out.count("| F") == REPORT.count("| F") - 1
    assert drop_failure_row(REPORT.replace("| F1 | 確かめた | 照合した |\n| F2 | 当てはまらない | 比べていない |\n", ""),
                            random.Random(0)) is None
    out, _ = add_claim(REPORT)
    assert "因果" in out[slice(*conclusion_span(out))]
    out, _ = swap_unit(REPORT)
    assert "1.85 m" in out


def test_every_mutation_says_whether_the_checks_should_catch_it():
    assert {m.expect for m in MUTATIONS} == {"caught", "not_checked"}
    assert all(callable(m.apply) for m in MUTATIONS)


def test_every_mutation_applies_through_the_list_with_an_rng():
    rng = random.Random(0)
    names = {m.name for m in MUTATIONS if m.apply(REPORT, rng) is not None}
    assert names == {m.name for m in MUTATIONS}


def test_drop_failure_row_leaves_other_tables_with_f_ids_alone():
    other = REPORT.replace("## 方法", "| F1 | B3 | 並べ替え | 通る |\n\n## 方法")
    for seed in range(10):
        out, note = drop_failure_row(other, random.Random(seed))
        assert "| F1 | B3 | 並べ替え | 通る |" in out


def test_perturb_number_says_whether_the_line_cites_an_output():
    report = REPORT.replace("平均の距離は 1.85 km ([表](outputs/summary.csv))。", "\n平均の距離は 1.85 km ([表](outputs/summary.csv))。")
    notes = {perturb_number(report, random.Random(s))[1] for s in range(30)}
    assert any(n.startswith("1.85 ->") and n.endswith("(cited)") for n in notes)
    assert any(n.startswith("4,232 ->") and n.endswith("(uncited)") for n in notes)
