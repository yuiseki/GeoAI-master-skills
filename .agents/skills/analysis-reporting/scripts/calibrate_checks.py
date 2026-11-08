"""Measure what check_project.py catches. Copy reports that already exist, break each copy in one known way, run the
check, and count how often the break shows up as a new problem. A check that has not been measured this way cannot
say how much its "ok" is worth.

    perturb_number   one number in 結論 changed, keeping its format (4,232 -> 4,528; 27.3% -> 27.6%)   caught
    swap_unit        the first "km" in 結論 written as "m" (the number stays)                       not_checked
    drop_section     データ removed                                                                 caught
    break_link       the first link into outputs/ pointed at a file that does not exist              caught
    drop_failure_row one row of the 失敗の型 table removed (reports that have the table)               caught
    add_claim        a causal sentence with no number added to 結論                                  not_checked

expect is what the checks are meant to do: caught, or not_checked (a claim in words; the checks do not read it).
Integers below 10 and numbers glued to a letter (M2, F4) are not perturbed: the checks pass them by design.

Usage:
    python3 calibrate_checks.py --repo <repository root> --out calibration.csv [--per-report 3] [--seed 0]
The tracked files of projects/ are copied to a temporary folder; the repository is not touched.
"""

import argparse
import csv
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

from check_report import _DATE, _LABEL, _NUM, _REFERENCE

Mutation = namedtuple("Mutation", "name apply expect")


def _label_lines(text):
    """(offset of the line, end of the line, name) for each section label."""
    out, pos = [], 0
    for line in text.splitlines(keepends=True):
        m = _LABEL.match(line.rstrip("\n"))
        if m:
            out.append((pos, pos + len(line), m.group(1)))
        pos += len(line)
    return out


def _span(text, name):
    labels = _label_lines(text)
    for i, (start, end, n) in enumerate(labels):
        if n == name:
            return start, end, labels[i + 1][0] if i + 1 < len(labels) else len(text)
    return None


def conclusion_span(text):
    s = _span(text, "結論")
    return (s[1], s[2]) if s else (0, 0)


def _mask(text):
    """Blank out link targets, figure numbers, row numbers and dates, keeping offsets."""
    for pattern in (_REFERENCE, _DATE):
        text = pattern.sub(lambda m: " " * len(m.group(0)), text)
    return text


def _candidates(text):
    a, b = conclusion_span(text)
    block = _mask(text[a:b])
    out = []
    for m in _NUM.finditer(block):
        t = m.group(0)
        if m.start() > 0 and re.match(r"[A-Za-z_]", block[m.start() - 1]):
            continue
        core = t.rstrip("%‰ ").replace(",", "").replace("−", "-").lstrip("-")
        if "e" in core.lower() or (("." not in core) and int(core) < 10):
            continue
        out.append((a + m.start(), a + m.end(), t))
    return out


def _changed(t):
    sign = t[0] if t[0] in "−-" else ""
    body = t[len(sign):]
    suffix = re.search(r" ?[%‰]$", body)
    suffix = suffix.group(0) if suffix else ""
    core = body[:len(body) - len(suffix)]
    if "." in core:
        new = core[:-1] + str((int(core[-1]) + 3) % 10)
    elif "," in core:
        new = f"{round(int(core.replace(',', '')) * 1.07):,}"
    else:
        new = core[:-1] + str((int(core[-1]) + 3) % 10)
    return sign + new + suffix


def perturb_number(text, rng):
    cands = _candidates(text)
    if not cands:
        return None
    a, b, t = rng.choice(cands)
    new = _changed(t)
    line = text[text.rfind("\n", 0, a) + 1:text.find("\n", b) if text.find("\n", b) >= 0 else len(text)]
    cited = "cited" if re.search(r"\]\([^)]*outputs/", line) else "uncited"
    return text[:a] + new + text[b:], f"{t} -> {new} ({cited})"


def swap_unit(text, rng=None):
    a, b = conclusion_span(text)
    m = re.search(r"(?<=\d) km\b", text[a:b])
    if not m:
        return None
    i = a + m.start()
    return text[:i] + " m" + text[i + 3:], "km -> m"


def drop_section(text, name="データ", rng=None):
    s = _span(text, name)
    if not s:
        return None
    return text[:s[0]] + text[s[2]:], f"no {name}"


def break_link(text, rng=None):
    m = re.search(r"\]\((\.?/?outputs/)([^)#\s]+)", text)
    if not m:
        return None
    return text[:m.start(2)] + "missing_" + text[m.start(2):], f"{m.group(2)} -> missing_{m.group(2)}"


def drop_failure_row(text, rng):
    s = _span(text, "失敗の型")
    if not s:
        return None
    rows = [m for m in re.finditer(r"^\|\s*F\d+\s*\|.*\n", text, re.MULTILINE) if s[1] <= m.start() < s[2]]
    if not rows:
        return None
    m = rng.choice(rows)
    return text[:m.start()] + text[m.end():], f"no {m.group(0).split('|')[1].strip()}"


def add_claim(text, rng=None):
    a, b = conclusion_span(text)
    if a == b:
        return None
    claim = "\nこの差は因果の効果であり、他の地域でも同じように起きる。\n"
    return text[:a] + claim + text[a:], "a causal claim in words"


MUTATIONS = [
    Mutation("perturb_number", perturb_number, "caught"),
    Mutation("swap_unit", swap_unit, "not_checked"),
    Mutation("drop_section", lambda text, rng: drop_section(text, "データ"), "caught"),
    Mutation("break_link", break_link, "caught"),
    Mutation("drop_failure_row", drop_failure_row, "caught"),
    Mutation("add_claim", add_claim, "not_checked"),
]


def _copy_tracked(repo, dest):
    files = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "projects"], capture_output=True,
                           check=True).stdout.decode().split("\0")
    for f in filter(None, files):
        target = dest / f
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / f, target)


def run(repo, out, per_report=3, seed=0):
    from check_project import check_project
    rng = random.Random(seed)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _copy_tracked(Path(repo), root)
        reports = sorted(root.glob("projects/**/report.md"))
        for report in reports:
            project = report.parent
            original = report.read_text(encoding="utf-8")
            base = set(check_project(project))
            for m in MUTATIONS:
                for k in range(per_report if m.name == "perturb_number" else 1):
                    got = m.apply(original, rng)
                    if got is None:
                        continue
                    report.write_text(got[0], encoding="utf-8")
                    new = sorted(set(check_project(project)) - base)
                    rows.append(dict(project=project.relative_to(root).as_posix(), mutation=m.name, expect=m.expect,
                                     change=got[1], caught=int(bool(new)), new_problems=" / ".join(new)[:300]))
            report.write_text(original, encoding="utf-8")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for m in MUTATIONS:
        r = [x for x in rows if x["mutation"] == m.name]
        if r:
            print(f"{m.name}\t{m.expect}\t{sum(x['caught'] for x in r)}/{len(r)}")
        for kind in ("cited", "uncited"):
            k = [x for x in r if x["change"].endswith(f"({kind})")]
            if k:
                print(f"{m.name} {kind}\t{m.expect}\t{sum(x['caught'] for x in k)}/{len(k)}")
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--per-report", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    run(Path(a.repo).resolve(), a.out, a.per_report, a.seed)


if __name__ == "__main__":
    sys.exit(main())
