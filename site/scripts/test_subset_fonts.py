"""uvx --python 3.12 --with fonttools --with pytest pytest -q test_subset_fonts.py"""

# Tests for subset-fonts.py: the character list of the OGP font subsets, and the subset and check steps.
# The Noto CJK sources, the report and card folders and the output folder are all pointed at tmp_path; the
# fonts are tiny TrueType fonts built in the test with fontTools.

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

SRC = Path(__file__).parent / "subset-fonts.py"
NAMES = ["NotoSerifJP-SemiBold.otf", "NotoSansJP-Bold.otf"]


def build_font(path: Path, chars: str):
    chars = "".join(dict.fromkeys(chars))
    names = [".notdef"] + [f"u{ord(c):04X}" for c in chars]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): f"u{ord(c):04X}" for c in chars})
    glyphs = {}
    for n in names:
        pen = TTGlyphPen(None)
        pen.moveTo((0, 0))
        pen.lineTo((0, 500))
        pen.lineTo((500, 500))
        pen.closePath()
        glyphs[n] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (600, 0) for n in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))


@pytest.fixture
def sf(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("subset_fonts", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for d in ("reports", "cards", "out", "src"):
        (tmp_path / d).mkdir()
    monkeypatch.setattr(mod, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(mod, "CARDS", tmp_path / "cards")
    monkeypatch.setattr(mod, "OUT", tmp_path / "out")
    monkeypatch.setattr(mod, "SOURCES", {n: tmp_path / "src" / f"{n}.ttf" for n in NAMES})
    monkeypatch.setattr(mod, "EXTRA", "…")
    return mod


def test_jis_x_0208_kanji_are_the_two_levels(sf):
    k = sf.jis_x_0208_kanji()
    # 2,965 level 1 and 3,390 level 2 kanji, from 亜 (16-01) to 熙 (84-06)
    assert len(k) == 2965 + 3390
    assert k[0] == "亜" and k[2964] == "腕" and k[2965] == "弌" and k[-1] == "熙"
    assert len(set(k)) == len(k)


def test_front_matter_is_read_only_between_the_fences(sf):
    (sf.REPORTS / "a.md").write_text("---\ntitle: 鬱\n---\n本文の字\n", encoding="utf-8")
    (sf.REPORTS / "b.md").write_text("no front matter 齟\n", encoding="utf-8")
    (sf.REPORTS / "c.txt").write_text("---\ntitle: 齬\n---\n", encoding="utf-8")
    assert sf.front_matter_text() == "title: 鬱"


def test_card_titles_are_the_first_heading_of_each_card_in_any_folder(sf):
    (sf.CARDS / "x").mkdir()
    (sf.CARDS / "x" / "one.md").write_text("intro\n# 第一の題\n## 小見出し\n# 二つ目\n", encoding="utf-8")
    (sf.CARDS / "two.md").write_text("# 𠮷野\n", encoding="utf-8")
    (sf.CARDS / "none.md").write_text("no heading\n", encoding="utf-8")
    assert sorted(sf.card_titles()) == sorted("第一の題𠮷野")


def test_charset_is_sorted_unique_and_has_no_control_characters(sf):
    (sf.REPORTS / "a.md").write_text("---\ntitle: 𠮷\n\tx\n---\n", encoding="utf-8")
    cs = sf.charset()
    assert list(cs) == sorted(set(cs))
    assert not set(cs) & set("\n\r\t")
    for c in " ~Aあアー、｡亜熙…𠮷":
        assert c in cs
    assert "\u007f" not in cs


def build_subsets(sf, chars):
    for n in NAMES:
        build_font(sf.OUT / n, chars)


def test_check_passes_when_every_needed_character_is_in_both_fonts(sf, capsys):
    (sf.REPORTS / "a.md").write_text("---\ntitle: 鬱\n---\n", encoding="utf-8")
    build_subsets(sf, "title: 鬱…")
    assert sf.check() == 0
    assert capsys.readouterr().err == ""


def test_check_fails_and_names_the_missing_characters(sf, capsys):
    (sf.REPORTS / "a.md").write_text("---\ntitle: 鬱\n---\n", encoding="utf-8")
    build_subsets(sf, "title: …")
    assert sf.check() == 1
    err = capsys.readouterr().err
    for n in NAMES:
        assert f"{n}: missing '鬱'" in err


def test_subset_keeps_only_the_character_list(sf, capsys):
    (sf.REPORTS / "a.md").write_text("---\ntitle: 鬱\n---\n", encoding="utf-8")
    # 𠮷 is in the source but in no list, so it must be dropped; 鬱 comes from the front matter
    for n, src in sf.SOURCES.items():
        build_font(src, "Aa あ亜鬱𠮷…title:")
    assert sf.subset() == 0
    for n in NAMES:
        cmap = TTFont(sf.OUT / n).getBestCmap()
        assert {ord(c) for c in "Aa あ亜鬱…"} <= set(cmap)
        assert ord("𠮷") not in cmap
    out = capsys.readouterr().out
    for n in NAMES:
        assert f"{n}: " in out and " bytes" in out


def test_subset_fails_when_a_font_is_too_big(sf, monkeypatch, capsys):
    for src in sf.SOURCES.values():
        build_font(src, "Aa")
    monkeypatch.setattr(sf, "MAX_BYTES", 10)
    assert sf.subset() == 1
    assert "is over 10 bytes" in capsys.readouterr().err


def test_subset_of_a_missing_source_fails_loudly(sf):
    with pytest.raises(OSError):
        sf.subset()
    assert not (sf.OUT / NAMES[0]).exists()


def test_cli_has_a_check_flag():
    r = subprocess.run([sys.executable, str(SRC), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--check" in r.stdout
