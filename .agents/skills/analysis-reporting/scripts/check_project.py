"""Check a whole project folder before the work is reported done. check_report.py checks one answer against the
evidence it is given; this finds the evidence itself, so a project cannot pass by leaving the evidence out.

    report       projects/<name>/report.md exists and passes check_report.py at the given level, with the evidence
                 taken from every UTF-8 text file in outputs/ (.csv .json .txt .log .md .tsv), plus the outputs/ of
                 every project the report links to (a synthesis quotes the projects it links to), plus any --evidence
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
import re
import sys
from pathlib import Path

from check_report import check, format_problems

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
    problems += [f"report.md: {p}" for p in format_problems(report, text) + check(text, level, evidence)]
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
