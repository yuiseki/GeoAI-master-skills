"""Known-answer tests for reading the Tohoku beech index table (uvx --with pytest pytest)."""

import pytest

import tohoku_index as ti

HEAD_X = [123, 166, 208, 251, 293, 336, 378, 421, 463, 506]


def head_words():
    return [{"text": "開花時" if i % 2 == 0 else "結実時", "x0": x + 3, "top": 75} for i, x in enumerate(HEAD_X)]


def chars_of(text, x, top, step=4):
    return [{"text": t, "x0": x + i * step, "top": top} for i, t in enumerate(text)]


def test_entries_join_split_characters_and_full_width_digits():
    cs = chars_of("並作（３", 123, 697) + chars_of(" . ", 139, 697) + chars_of("4）", 151, 697)
    assert ti.entries(cs) == [(123, 697, "並作", 3.4)]


def test_characters_of_one_entry_on_slightly_different_tops_stay_together():
    cs = chars_of("並作（", 123, 144.6) + chars_of("2.1）", 135, 145.4)
    assert [e[2:] for e in ti.entries(cs)] == [("並作", 2.1)]


def test_table_assigns_columns_and_the_nearest_year_label():
    words = head_words() + [{"text": "1990", "x0": 95, "top": 111}, {"text": "2 0 2 6", "x0": 96, "top": 697}]
    cs = (chars_of("並作（3.4）", 123, 108) + chars_of("凶作（1.6）", 421, 108)
          + chars_of("豊作（4.4）", 506, 697))
    rows = ti.table(cs, words)
    assert rows == {(1990, "青森県", "flowering"): (3.4, "並作"), (1990, "秋田県", "fruiting"): (1.6, "凶作"),
                    (2026, "山形県", "fruiting"): (4.4, "豊作")}


def test_an_entry_far_from_any_year_or_column_stops():
    words = head_words() + [{"text": "1990", "x0": 95, "top": 111}]
    with pytest.raises(ValueError):
        ti.table(chars_of("並作（3.4）", 123, 200), words)
    with pytest.raises(ValueError):
        ti.table(chars_of("並作（3.4）", 145, 111), words)


def test_classes_follow_the_index_thresholds():
    assert ti.check_class(3.5, "豊作") and ti.check_class(3.4, "並作") and ti.check_class(2.0, "並作")
    assert ti.check_class(1.0, "凶作") and ti.check_class(0.9, "大凶作") and ti.check_class(0.0, "皆無")
    assert not ti.check_class(1.9, "並作")
    assert not ti.check_class(2.0, "凶作") and ti.at_boundary(2.0, "凶作")  # rounded up onto the threshold
    assert not ti.at_boundary(2.1, "凶作") and not ti.at_boundary(2.0, "大凶作")


def test_release_counts_and_the_index_formula():
    text = " 秋田県   19   18   14    0    51       3.2     並作\n 計    65   45   24    7    141\n"
    assert ti.release_counts(text) == {"秋田県": (19, 18, 14, 0, 51, 3.2)}
    assert ti.index_from_counts(19, 18, 14, 0, 51) == pytest.approx(163 / 51)
    with pytest.raises(ValueError):
        ti.index_from_counts(1, 1, 1, 1, 5)
