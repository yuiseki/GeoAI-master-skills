"""Set a Japanese font for matplotlib, and stop when the figure's text has characters the font cannot draw.

    python cjk_font.py "図に使う全ての文字"          # prints the font it would use, or exits 1
    python cjk_font.py --font "IPAexGothic" "東京"

In a script:

    from cjk_font import use_cjk_font
    use_cjk_font("東京都 23 区の人口 (人)")   # call before drawing; pass every label, title and tick text

Without a Japanese font matplotlib does not fail: it warns "Glyph ... missing from font(s) DejaVu Sans" and
saves a figure with empty boxes (tofu). This module turns that into an error. It picks the first installed font
of PREFERRED; if there is none, it tries matplotlib-fontja (a pip package that bundles IPAexGothic). The minus
sign (U+2212) of negative tick labels is checked too, and swapped for a hyphen if the font lacks it.
"""

import argparse
import sys

import matplotlib
from matplotlib import font_manager as fm
from matplotlib.ft2font import FT2Font

PREFERRED = ["Noto Sans CJK JP", "Noto Sans JP", "Source Han Sans JP", "IPAexGothic", "IPAGothic",
             "Hiragino Sans", "Yu Gothic", "TakaoGothic"]
MINUS = "−"


def installed():
    """Font family name -> file, for every font matplotlib knows."""
    return {f.name: f.fname for f in fm.fontManager.ttflist}


def pick_font(names, preferred=PREFERRED):
    return next((p for p in preferred if p in names), None)


def missing_glyphs(text, font_path):
    """The characters of text (each once, in order, spaces aside) that the font has no glyph for."""
    cmap = FT2Font(font_path).get_charmap()
    seen = []
    for ch in text:
        if not ch.isspace() and ord(ch) not in cmap and ch not in seen:
            seen.append(ch)
    return seen


def use_cjk_font(text="日本語", font=None):
    """Make font (or the first preferred Japanese font) matplotlib's default and return its name.
    Stops (SystemExit) when no Japanese font is available or the font lacks a character of text."""
    fonts = installed()
    name = font or pick_font(fonts)
    if name is None:
        try:
            import matplotlib_fontja  # noqa: F401  registers IPAexGothic and makes it the default
        except ImportError:
            raise SystemExit("no Japanese font for matplotlib: install one (pip install matplotlib-fontja "
                             "bundles IPAexGothic), or write the labels without Japanese") from None
        fonts = installed()
        name = pick_font(fonts)
        if name is None:
            raise SystemExit("matplotlib-fontja is installed but its font was not found")
    if name not in fonts:
        raise SystemExit(f"font {name!r} is not installed; installed Japanese fonts: "
                         f"{[p for p in PREFERRED if p in fonts]}")
    lacking = missing_glyphs(text, fonts[name])
    if lacking:
        raise SystemExit(f"font {name!r} cannot draw {''.join(lacking)!r}: choose another font or other words")
    matplotlib.rcParams["font.family"] = [name]
    if missing_glyphs(MINUS, fonts[name]):
        matplotlib.rcParams["axes.unicode_minus"] = False
    return name


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("text", help="every character the figure will show")
    p.add_argument("--font", help="use this font family instead of the first preferred one")
    a = p.parse_args()
    try:
        print(use_cjk_font(a.text, a.font))
    except SystemExit as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
