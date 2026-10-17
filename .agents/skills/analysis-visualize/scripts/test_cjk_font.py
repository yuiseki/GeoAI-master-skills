"""uvx --with matplotlib --with pytest pytest test_cjk_font.py"""

import subprocess
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

import cjk_font  # noqa: E402

HERE = Path(__file__).parent
DEJAVU = fm.findfont("DejaVu Sans")   # ships with matplotlib, has no kanji
HOST_CJK = cjk_font.pick_font(cjk_font.installed())


def test_missing_glyphs_lists_the_characters_a_font_cannot_draw():
    assert cjk_font.missing_glyphs("東京 23 区 abc", DEJAVU) == ["東", "京", "区"]


def test_missing_glyphs_ignores_spaces_and_counts_each_character_once():
    assert cjk_font.missing_glyphs("東 東\n東", DEJAVU) == ["東"]


def test_pick_font_follows_the_preference_order():
    names = {"IPAexGothic": "a.ttf", "DejaVu Sans": "b.ttf", "Noto Sans CJK JP": "c.ttc"}
    assert cjk_font.pick_font(names) == "Noto Sans CJK JP"
    assert cjk_font.pick_font({"DejaVu Sans": "b.ttf"}) is None


def test_no_japanese_font_stops_with_what_to_do(monkeypatch):
    # in the eval images there is no CJK font and no matplotlib-fontja: matplotlib only warns and saves tofu
    monkeypatch.setattr(cjk_font, "installed", lambda: {"DejaVu Sans": DEJAVU})
    monkeypatch.setitem(sys.modules, "matplotlib_fontja", None)   # import fails
    with pytest.raises(SystemExit, match="matplotlib-fontja"):
        cjk_font.use_cjk_font("東京")


def test_a_named_font_without_the_characters_stops(monkeypatch):
    monkeypatch.setattr(cjk_font, "installed", lambda: {"DejaVu Sans": DEJAVU})
    with pytest.raises(SystemExit, match="東京"):
        cjk_font.use_cjk_font("東京", font="DejaVu Sans")


def test_a_font_that_is_not_installed_stops(monkeypatch):
    monkeypatch.setattr(cjk_font, "installed", lambda: {"DejaVu Sans": DEJAVU})
    with pytest.raises(SystemExit, match="not installed"):
        cjk_font.use_cjk_font("abc", font="No Such Font")


@pytest.mark.skipif(HOST_CJK is None, reason="no Japanese font on this machine")
def test_with_the_font_set_a_japanese_title_draws_without_missing_glyphs():
    name = cjk_font.use_cjk_font("東京都 23 区の人口 −1.5")
    assert name == HOST_CJK and matplotlib.rcParams["font.family"][0] == name
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig, ax = plt.subplots()
        ax.set_title("東京都 23 区の人口")
        ax.plot([-1, 1], [-1.5, 2])   # negative tick labels use the minus sign
        fig.canvas.draw()
        plt.close(fig)
    assert not [w for w in caught if "missing from font" in str(w.message)]


def test_command_line_exits_1_and_names_the_missing_characters():
    r = subprocess.run([sys.executable, str(HERE / "cjk_font.py"), "--font", "DejaVu Sans", "区の数"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "区" in r.stderr and "数" in r.stderr
