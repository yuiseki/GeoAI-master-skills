"""Subset the Noto CJK JP fonts used to draw OGP images.

satori needs static OTF/TTF files, and the full fonts are about 17MB each.
The subsets keep ASCII, kana, Japanese punctuation, JIS X 0208 level 1 and 2
kanji and every character in the report front matter, so new titles usually
render without regenerating the fonts.

Run from site/:
  uv run --no-project --with fonttools python3 scripts/subset-fonts.py
  uv run --no-project --with fonttools python3 scripts/subset-fonts.py --check
"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

from fontTools.subset import main as pyftsubset
from fontTools.ttLib import TTFont

SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "src/assets/fonts"
REPORTS = SITE / "src/content/reports"
SOURCES = {
    # Debian fonts-noto-cjk 1:20230817; index 0 of each collection is JP.
    "NotoSerifJP-SemiBold.otf": Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-SemiBold.ttc"),
    "NotoSansJP-Bold.otf": Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
}
EXTRA = "yuiseki の GeoAI 研究所…・×〜—–"
MAX_BYTES = 5_000_000


def jis_x_0208_kanji() -> str:
    # Rows 16-47 are level 1, rows 48-84 level 2; EUC-JP bytes are row + 0xA0.
    chars = []
    for row in range(16, 85):
        for cell in range(1, 95):
            try:
                chars.append(bytes([row + 0xA0, cell + 0xA0]).decode("euc_jp"))
            except UnicodeDecodeError:
                pass
    return "".join(chars)


def front_matter_text() -> str:
    text = []
    for path in sorted(REPORTS.glob("*.md")):
        match = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
        if match:
            text.append(match.group(1))
    return "".join(text)


def charset() -> str:
    ranges = [
        (0x20, 0x7E),      # ASCII
        (0x2010, 0x2027),  # general punctuation
        (0x3000, 0x303F),  # CJK symbols and punctuation
        (0x3040, 0x30FF),  # hiragana and katakana
        (0xFF01, 0xFF9F),  # full-width and half-width forms
    ]
    chars = {chr(c) for start, end in ranges for c in range(start, end + 1)}
    chars |= set(jis_x_0208_kanji()) | set(front_matter_text()) | set(EXTRA)
    return "".join(sorted(c for c in chars if c not in "\n\r\t"))


def check() -> int:
    needed = set(front_matter_text()) | set(EXTRA)
    needed -= set("\n\r\t")
    failed = 0
    for name in SOURCES:
        cmap = TTFont(OUT / name).getBestCmap()
        missing = sorted(c for c in needed if ord(c) not in cmap)
        if missing:
            print(f"{name}: missing {''.join(missing)!r}", file=sys.stderr)
            failed = 1
    return failed


def subset() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
        handle.write(charset())
        text_file = handle.name
    try:
        for name, source in SOURCES.items():
            out = OUT / name
            pyftsubset([
                str(source), "--font-number=0", f"--text-file={text_file}", f"--output-file={out}",
                "--layout-features=kern,palt", "--notdef-glyph", "--notdef-outline",
                "--name-IDs=*", "--drop-tables+=DSIG",
            ])
            size = out.stat().st_size
            print(f"{name}: {size:,} bytes")
            if size > MAX_BYTES:
                print(f"{name} is over {MAX_BYTES:,} bytes; the character list is probably wrong", file=sys.stderr)
                return 1
    finally:
        Path(text_file).unlink()
    return check()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="only check that the subsets cover the front matter")
    sys.exit(check() if parser.parse_args().check else subset())
