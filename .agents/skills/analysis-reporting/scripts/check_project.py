"""Check a whole project folder before the work is reported done. check_report.py checks one answer against the
evidence it is given; this finds the evidence itself, so a project cannot pass by leaving the evidence out.

    report       projects/<name>/report.md exists and passes check_report.py at the given level, with the evidence
                 taken from every UTF-8 text file in outputs/ (.csv .json .txt .log .md .tsv), plus the outputs/ of
                 every project the report links to (a synthesis quotes the projects it links to), plus any --evidence
    cited        a table row or sentence that links to files in an outputs/ folder has its numbers traced in those
                 files only (their names included: top20_delta.csv holds a 20), so a wrong number cannot pass by
                 matching an unrelated table. Integers below 10 and settings written in 問い or 方法 (100 m, 65 歳)
                 may come from anywhere. Each row of the 要点 table in 結論 that states a number must cite at least
                 one such file
    readers      every number in the Markdown files under reports/ (reports for each reader) is traced the same way
    links        every relative link and image in report.md points at a file that exists (anchors and URLs are not
                 checked, nor links inside code blocks)
    encoding     every text file in the project is UTF-8. A Windows default (cp932) is the usual cause; write text
                 with encoding='utf-8'
    readme       README.md exists, to say what the project is and how to run it again

Usage:
    python3 check_project.py projects/<name> [more projects ...] [--level simple|standard|full] [--evidence F ...]
Prints "<project>: ok" or one line per problem. Exit status 1 when any project has a problem.
"""

import argparse
import os
import re
import sys
from pathlib import Path

from check_report import _REFERENCE, check, format_problems, numbers_in, sections, traceable

TEXT = {".csv", ".json", ".txt", ".log", ".md", ".tsv", ".py", ".yaml", ".yml", ".toml"}
EVIDENCE = {".csv", ".json", ".txt", ".log", ".md", ".tsv"}
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


def _targets(text):
    """Relative link targets in Markdown, without anchors; URLs, mail and in-page anchors are not files."""
    text = _FENCE.sub("", text)
    out = []
    for m in _LINK.finditer(text):
        target = m.group(1)
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("#"):
            continue
        target = target.split("#")[0].split("?")[0]
        if target:
            out.append(target)
    return out


def dead_links(report):
    """Link targets in the report that do not exist, relative to the report."""
    report = Path(report)
    return [t for t in _targets(report.read_text(encoding="utf-8")) if not (report.parent / t).exists()]


def not_utf8(project):
    """Text files under the project, relative to it, that do not decode as UTF-8."""
    bad = []
    for path in sorted(Path(project).rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT and "__pycache__" not in path.parts:
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                bad.append(path.relative_to(project).as_posix())
    return bad


def _outputs_text(project):
    texts = []
    outputs = Path(project) / "outputs"
    if outputs.is_dir():
        for path in sorted(outputs.rglob("*")):
            if path.is_file() and path.suffix.lower() in EVIDENCE:
                try:
                    texts.append(path.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    pass  # reported by not_utf8
    return texts


def evidence_for(project, report_text, extra=()):
    """The outputs of the project, of every project the report links to, and any extra files, as one text."""
    project = Path(project).resolve()
    texts = _outputs_text(project)
    seen = {project}
    for target in _targets(report_text):
        path = (project / target).resolve()
        linked = path if path.is_dir() else path.parent
        while linked != linked.parent and not (linked / "report.md").exists():
            linked = linked.parent
        if (linked / "report.md").exists() and linked not in seen:
            seen.add(linked)
            texts += _outputs_text(linked)
    texts += [Path(f).read_text(encoding="utf-8") for f in extra]
    return "\n".join(texts)


def _cited(line, base):
    """Files in an outputs/ folder that the line links to, and the line with those links taken out (a file name such
    as b1_main.json is not a number to trace)."""
    files = []
    for m in _LINK.finditer(line):
        target = m.group(1).split("#")[0]
        path = (Path(base) / target).resolve() if target and not re.match(r"^[a-z][a-z0-9+.-]*:", target) else None
        if path is not None and path.is_file() and "outputs" in path.parts and path.suffix.lower() in EVIDENCE:
            files.append(path)
            line = line.replace(m.group(0), " ")
    return files, line


def _segments(line):
    """A table row is one claim; prose is split into sentences, so a link in one sentence scopes only that sentence."""
    if line.lstrip().startswith("|"):
        return [line]
    return [x for x in re.split(r"(?<=。)", line) if x.strip()]


def _trace_lines(lines, base, project, evidence, label, uncited=True, settings=()):
    """Problems for numbers in the lines. A segment (table row or sentence) that cites outputs is traced in those
    files; the rest in evidence, unless uncited is False (the caller traces them). Also returns the segments that cited something, so the
    caller does not trace them twice."""
    problems, cited = [], []
    for line in lines:
        for segment in _segments(line):
            files, rest = _cited(segment, base)
            if files:
                cited.append(segment)
                # a file's name says what it holds (top20_delta.csv holds the top 20)
                text = "\n".join(f.name + "\n" + f.read_text(encoding="utf-8") for f in files)
                names = " or ".join(os.path.relpath(f, Path(project).resolve()).replace(os.sep, "/") for f in files)
                missing = traceable(rest, text)
                if evidence is not None:
                    # a small integer (7 年, 上位 5) matches by chance in any file, so scoping it adds nothing;
                    # it may come from any output
                    missing = [t for t in missing if not (re.fullmatch(r"\d", t) and not traceable(t, evidence))]
                # a setting stated in 問い or 方法 (100 m, 800 m, 65 歳) is a definition, not a value of the file
                missing = [t for t in missing if t not in settings]
                problems += [f"{label}: {t} is not in {names}" for t in missing]
            elif uncited and evidence is not None:
                problems += [f"{label}: {t} does not appear in the evidence" for t in traceable(segment, evidence)]
    return problems, cited


def _key_rows(conclusion):
    """Data rows of the 要点 table in the conclusion, numbered from 1."""
    rows, inside = [], False
    for line in conclusion:
        if line.startswith("|") and "要点" in line and not inside:
            inside = True
        elif inside and line.startswith("|"):
            if not re.match(r"^\|[\s:|-]+\|?$", line):
                rows.append(line)
        elif inside:
            break
    return rows


def check_project(project, level="full", extra=()):
    project = Path(project)
    problems = [f"{f} is not UTF-8: write text outputs with encoding='utf-8'" for f in not_utf8(project)]
    report = project / "report.md"
    if not report.exists():
        return problems + ["report.md is missing"]
    if not (project / "README.md").exists():
        problems.append("README.md is missing: say what the project is and how to run it again")
    try:
        text = report.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return problems
    problems += [f"report.md: links to {t}, which does not exist" for t in dead_links(report)]
    evidence = evidence_for(project, text, extra)
    conclusion = sections(text).get("結論", [])
    for i, row in enumerate(_key_rows(conclusion), 1):
        # a row that states no number has nothing to trace (the row number in the first cell is not one)
        if numbers_in(re.sub(r"^\|\s*\d+\s*\|", "|", _REFERENCE.sub(" ", row))) and not _cited(row, project)[0]:
            problems.append(f"report.md: 要点 row {i} cites no file in outputs/: link the output each number comes from")
    parts = sections(text)
    settings = {t for name in ("問い", "方法") for t, *_ in numbers_in("\n".join(parts.get(name, [])))}
    scoped, cited = _trace_lines(conclusion, project, project, evidence, "report.md", uncited=False, settings=settings)
    # segments that cite their outputs were traced above; check_report traces the rest of 結論 against all evidence
    rest = text
    for segment in cited:
        rest = rest.replace(segment, "（出典つき）")
    # settings written in 問い and 方法 are definitions, so the rest of 結論 may repeat them too
    definitions = "\n".join(parts.get("問い", []) + parts.get("方法", []))
    problems += [f"report.md: {p}" for p in format_problems(report, text) + check(rest, level, evidence + "\n" + definitions)]
    problems += scoped
    for reader in sorted((project / "reports").rglob("*.md")) if (project / "reports").is_dir() else []:
        try:
            body = _FENCE.sub("", reader.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
        label = reader.relative_to(project).as_posix()
        problems += _trace_lines(body.splitlines(), reader.parent, project, evidence, label, settings=settings)[0]
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("projects", nargs="+")
    p.add_argument("--level", choices=["simple", "standard", "full"], default="full")
    p.add_argument("--evidence", nargs="*", default=(), help="more files with outputs the report used")
    a = p.parse_args()
    failed = False
    for project in a.projects:
        problems = check_project(project, a.level, a.evidence)
        failed |= bool(problems)
        for x in problems or ["ok"]:
            print(f"{project}: {x}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
