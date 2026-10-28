"""Tests for the legend mapping: by code only, every legend in Akita, the names checked against the codes."""

import pytest

import mapping

LEGENDS = [("110100", "チシマザサ－ブナ群団", "ブナクラス域自然植生"), ("190100", "ウラジロヨウラク－ミヤマナラ群団", "ブナクラス域自然植生"),
           ("220501", "オクチョウジザクラ－コナラ群集", "ブナクラス域代償植生"), ("540100", "スギ・ヒノキ・サワラ植林", "植林地・耕作地植生")]


def test_assigned_codes_and_categories():
    assert set(mapping.CATEGORY.values()) == {"beech", "beech_mizunara", "mizunara", "konara"}
    assert len(mapping.CATEGORY) == 10
    assert mapping.CATEGORY["220100"] == "beech_mizunara"
    assert "190100" not in mapping.CATEGORY  # ミヤマナラ is not counted as an oak forest


def test_table_covers_every_legend_and_marks_the_rest_none():
    rows = mapping.table(LEGENDS, check_all=False)
    assert [r["凡例コード"] for r in rows] == ["110100", "190100", "220501", "540100"]
    by = {r["凡例コード"]: r for r in rows}
    assert by["110100"]["category"] == "beech" and by["220501"]["category"] == "konara"
    assert by["190100"]["category"] == "none" and "ミヤマナラ" in by["190100"]["reason"]
    assert by["540100"]["category"] == "none" and by["540100"]["reason"]


def test_a_name_that_does_not_match_its_code_stops():
    with pytest.raises(ValueError):
        mapping.table([("110100", "ブナ二次林", "x")], check_all=False)


def test_all_assigned_codes_must_be_present():
    with pytest.raises(ValueError):
        mapping.table(LEGENDS)
