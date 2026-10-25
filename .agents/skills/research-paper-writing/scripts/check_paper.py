"""Check only mechanical properties of a GitHub-readable paper.md.

Usage: python3 scripts/check_paper.py projects/<name>/paper.md
This cannot verify results, citations, causal claims, or whether the prose is a good paper.
"""

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

PAGE_TAG = re.compile(r"<\s*(?:!doctype|html|head|body|script|style|iframe|div)\b", re.IGNORECASE)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
IMAGE = re.compile(r"!\[[^]]*\]\(([^)]+)\)")
SECTIONS = {
    "Abstract": ("要旨", "abstract"),
    "Data": ("データ", "資料", "data"),
    "Methods": ("方法", "分析方法", "methods", "methodology"),
    "Results": ("結果", "分析結果", "results"),
    "Limitations": ("限界", "頑健性", "頑健性と限界", "robustness", "limitations"),
}


def visible_lines(text):
    """Return Markdown outside fences and report an unclosed fenced block."""
    visible = []
    opener = None
    for line_number, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if opener is None:
            if match:
                opener = (match.group(1)[0], len(match.group(1)), line_number)
            else:
                visible.append(line)
        elif match and match.group(1)[0] == opener[0] and len(match.group(1)) >= opener[1] and not match.group(2).strip():
            opener = None
    return visible, (f"unclosed fenced block at line {opener[2]}" if opener else None)


def heading_name(heading):
    """Ignore a section number while retaining its subject."""
    return re.sub(r"^\d+(?:\.\d+)*[.．]?\s*", "", heading).strip().lower()


def check_paper(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    problems = []
    if path.suffix.lower() != ".md":
        problems.append("write the paper in Markdown (.md)")
    if PAGE_TAG.search(text):
        problems.append("HTML page markup is not allowed in paper.md")

    lines, fence_problem = visible_lines(text)
    if fence_problem:
        problems.append(fence_problem)
    if not any(re.match(r"^#\s+\S", line) for line in lines):
        problems.append("Title: add a nonempty H1 heading")
    headings = [heading_name(match.group(1)) for line in lines if (match := HEADING.match(line))]
    for label, aliases in SECTIONS.items():
        if not any(any(name == alias or name.startswith(alias + " ") for alias in aliases) for name in headings):
            problems.append(f"{label}: missing section heading")

    for line in lines:
        for match in IMAGE.finditer(line):
            target = match.group(1).split()[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path.lower().endswith(".png"):
                continue
            image_path = path.parent / unquote(parsed.path)
            if not image_path.is_file():
                problems.append(f"PNG image is missing: {target}")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper", type=Path)
    args = parser.parse_args()
    problems = check_paper(args.paper)
    for problem in problems:
        print(problem)
    print("ok" if not problems else f"{len(problems)} problems")
    raise SystemExit(bool(problems))


if __name__ == "__main__":
    main()
