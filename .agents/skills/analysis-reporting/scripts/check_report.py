"""Check a final answer's minimal structure before it is sent. It reorganises nothing and recomputes nothing: it
reads the answer and, optionally, the outputs it was written from.

    format       the answer is a Markdown file (.md) with no HTML page markup (<!DOCTYPE>, <html>, <body>, <script>,
                 <style>, <iframe>, <div>). A figure goes in as a PNG (![...](outputs/map.png)); an interactive HTML
                 page, when one was asked for, is a separate file the report links to, not the report.

    sections     the answer's parts, by label ("問い: ...") or heading ("## 問い"), in order
    check        the fixed minimum, for a level of detail:
                   問い     present, first, one line
                   結論     present, second (the answer comes before how it was reached)
                   データ   present; names a version or a date (or says 版は未確認)
                   方法     present
                   確かめていないこと  required at "full"; optional otherwise
                 and a length budget: simple at most 8 non-empty lines, standard at most 40, full no limit
    traceable    every number in 結論 must appear in the evidence (tool outputs, logs, the commands run), up to
                 rounding at the conclusion's own precision (82% matches 0.8183; 0.45 does not match 0.4446). A
                 value on the tie matches either way (5.66 and 5.67 both match 5.665).
                 Dates and years (2011 年, 1981〜2000年) are skipped, and so are a 1 that names a unit (1 人あたり), figure and table numbers (図 1,
                 表 2; but not a word ending in 図 or 表, as in 箇所表 0.61, and not a decimal), link targets
                 (#図-1-..., ../other/report.md) and the row number in a table's first cell. A distance in km also
                 matches the evidence in metres (1 km against --catchment 1000). In the evidence, a comma-grouped
                 number also counts as its parts, so a CSV row such as 285,245,13 holds 285, 245 and 13. A number the
                 evidence does not hold was computed or remembered somewhere else: find where, or take it out.

Usage:
    python3 check_report.py ANSWER.md --level simple|standard|full [--evidence OUTPUT.txt ...]
Exit status 1 when something is missing.
"""

import argparse
import re
import sys

REQUIRED = ["問い", "結論", "データ", "方法"]
OPTIONAL = ["確かめていないこと"]
LIMITS = {"simple": 8, "standard": 40, "full": None}
_LABEL = re.compile(r"^\s*(?:#{1,6}\s*)?(問い|結論|データ|方法|確かめていないこと)\s*(?:[:：]\s*(.*))?$")
_PAGE = re.compile(r"<\s*(?:!doctype|html|head|body|script|style|iframe|div)\b", re.IGNORECASE)
# a date (2026-10-31, 2026-10) and a year: one followed by 年, or either end of a range of years (1981〜2000年)
_YEAR = r"(?<![\d,.])(?:1[89]|20)\d{2}"
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|" + _YEAR + r"\s*(?:[〜~–-]\s*" + _YEAR + r")?\s*年")
# a comma is a thousands separator only between groups of three digits (1,168,211); otherwise it separates two
# numbers, as in a CSV row written without spaces (1400,8.4293)
_NUM = re.compile(r"[−-]?(?:\d{1,3}(?:,\d{3})+(?![\d])|\d+)(?:\.\d+)?(?:[eE][-+]\d+(?![\d.]))?%?")
_VERSION = re.compile(r"\d{4}-\d{2}|\d{4} ?年|版|v\d|version|\d+\.\d+")


def sections(text):
    """{name: [lines]} in the order they appear; a section runs until the next label or heading."""
    out, current = {}, None
    for line in text.splitlines():
        m = _LABEL.match(line)
        if m:
            current = m.group(1)
            out[current] = [m.group(2)] if m.group(2) else []
        elif current is not None and line.strip():
            out[current].append(line.strip())
    return out


# references, not results: a link target (#図-1-件数の推移, ../grid-100m/report.md), a figure or table number (図 1,
# 表 2) and the row number in the first cell of a table (| 3 | ...)
# 図 and 表 after another kanji are part of a word (箇所表 0.61, 地図 9 枚), and a reference number is whole, not a
# decimal (図 0.61 is a value)
_REFERENCE = re.compile(r"\]\([^)]*\)|(?<![\u4e00-\u9fff])[図表]\s*\d+(?![\d.])|^\|\s*\d+\s*(?=\|)", re.MULTILINE)
_PER_UNIT = re.compile(r"\s*(?:[^\s\d]{1,3}\s*)?あたり|\s*[人校件台]に")
_KM = re.compile(r"\s*km")


def numbers_in(text, units=False):
    """(text, value, decimals, is_percent) for each number, dates left out, and "1" used to name a unit ("1 人あたり",
    "1 校に") left out. units=True adds a fifth item: True when the number is followed by km."""
    text = _DATE.sub(" ", text)
    out = []
    for m in _NUM.finditer(text):
        t = m.group(0)
        after = text[m.end():m.end() + 6]
        if t == "1" and _PER_UNIT.match(after):
            continue
        pct = t.endswith("%")
        core = t.rstrip("%").replace(",", "").replace("−", "-")
        mantissa, _, exponent = core.lower().partition("e")
        dec = len(mantissa.split(".")[1]) if "." in mantissa else 0
        dec = max(dec - int(exponent), 0) if exponent else dec
        item = (t, float(core), dec, pct)
        out.append(item + (bool(_KM.match(after)),) if units else item)
    return out


def traceable(conclusion, evidence):
    """The conclusion's numbers that no evidence number rounds to. References in the conclusion are skipped. In the
    evidence, a number grouped by commas is also read as its parts, since a CSV row of three-digit values
    (285,245,13) looks like a thousands-grouped number."""
    conclusion = _REFERENCE.sub(" ", conclusion)
    ev = []
    for t, v, _, _ in numbers_in(evidence):
        ev.append(v)
        if "," in t:
            ev += [float(x.rstrip("%").replace("−", "-")) for x in t.split(",") if x.strip("%−-")]
    missing = []
    for t, v, dec, pct, km in numbers_in(conclusion, units=True):
        candidates = ev + ([e * 100 for e in ev] if pct else []) + ([e / 1000 for e in ev] if km else [])
        # within half a unit of the conclusion's last digit, a tie included: an output's 5.665 may be written 5.66
        # or 5.67, since the output may itself be rounded from 5.6649 or 5.6651
        half = 0.5 * 10 ** -dec + 10 ** -(dec + 6)
        if not any(abs(e - v) <= half or abs(-e - v) <= half for e in candidates):
            missing.append(t)
    return missing


def format_problems(path, text):
    """The report must be Markdown: a .md file, not an HTML page."""
    problems = []
    if not str(path).lower().endswith(".md"):
        problems.append(f"{path}: write the report in Markdown (.md), not as HTML, a notebook or another format")
    tags = sorted({m.group(0).lower() for m in _PAGE.finditer(text)})
    if tags:
        problems.append(f"HTML page markup in the report ({', '.join(tags)}): write it in Markdown; put figures in as "
                        "PNG images and link an interactive page as a separate file")
    return problems


def check(text, level, evidence=None):
    if level not in LIMITS:
        raise ValueError(f"level is one of {list(LIMITS)}")
    problems = []
    s = sections(text)
    for name in REQUIRED:
        if name not in s or not any(x.strip() for x in s[name]):
            problems.append(f"{name}: missing or empty")
    order = [k for k in s if k in REQUIRED]
    if order != [k for k in REQUIRED if k in s]:
        problems.append(f"sections out of order: {order}; the order is {REQUIRED}")
    if "問い" in s and len([x for x in s["問い"] if x.strip()]) > 1:
        problems.append("問い: write the question in one line")
    if "データ" in s and not _VERSION.search(" ".join(s["データ"])) and "未確認" not in " ".join(s["データ"]):
        problems.append("データ: give each dataset's version or date (or write 版は未確認)")
    if level == "full" and not any(x.strip() for x in s.get("確かめていないこと", [])):
        problems.append("確かめていないこと: a full report says what was not checked")
    limit = LIMITS[level]
    lines = [x for x in text.splitlines() if x.strip()]
    if limit is not None and len(lines) > limit:
        problems.append(f"{len(lines)} non-empty lines for a {level} answer (at most {limit}); shorten it or "
                        "choose the level the analysis needs")
    if evidence is not None and "結論" in s:
        for t in traceable("\n".join(s["結論"]), evidence):
            problems.append(f"結論: {t} does not appear in the evidence")
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("answer")
    p.add_argument("--level", choices=list(LIMITS), required=True)
    p.add_argument("--evidence", nargs="*", default=None, help="files with the outputs and commands the answer used")
    a = p.parse_args()
    text = open(a.answer, encoding="utf-8").read()
    ev = None if a.evidence is None else "\n".join(open(f, encoding="utf-8").read() for f in a.evidence)
    problems = format_problems(a.answer, text) + check(text, a.level, ev)
    for x in problems:
        print(x)
    print("ok" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
