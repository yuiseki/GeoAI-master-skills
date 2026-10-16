"""Check that every skill stands alone.

    python3 check_skills.py

1. No skill points at another skill's files (a relative path, or a script path built from parents[2]).
2. No skill names another skill, except dataset-discovery (the catalogue of dataset facts) and its own name.
3. A script shared by several skills is a copy, and so is its test; the copies must be identical.
4. Every dataset, catalog and service reference in dataset-discovery starts with YAML frontmatter that has the required keys,
   and every `joins` entry points at a dataset and table that exist (needs PyYAML). The index (index.md) has none.
5. No Markdown under .agents/skills uses bold or an em dash (code spans and code blocks aside).
6. Every script in a scripts/ directory has its test_<name>.py beside it.
7. TODO.md agrees with the files: a checked skill has a SKILL.md with content (an empty one is a stub), every
   reference it lists exists when checked, every reference file is listed, and each stage's (done / all) count holds.
8. The uvx command on the first line of each test brings every third-party package the test and its script import.
"""

import filecmp
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is needed to check the dataset frontmatter: uvx --with pyyaml python check_skills.py")

COMMON = ["id", "description", "url", "license", "spatial_coverage", "temporal_coverage"]
REQUIRED = {
    "dataset": COMMON + ["contents", "tables"],
    "catalog": COMMON + ["contents", "access"],
    "service": COMMON + ["protocol", "operations"],
}
JOINS = re.compile(r"^(?:([\w-]+):)?([\w*]+)\.")


def read_frontmatter(path):
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    return yaml.safe_load(text.split("---\n", 2)[1])


FLOW = re.compile(r"^\s*(?:-\s+)?(?:[\w.\"-]+:\s+)?[\[{](?!\]\s*$|\}\s*$)")


def column_type(fm, table, column):
    for t in fm.get("tables", []):
        if t["name"] == table:
            for x in t.get("join_keys", []) + t.get("columns", []):
                if x.get("column", x.get("name")) == column:
                    return x.get("type")
    return None


def broken_values(obj, path=""):
    """Values that look cut in the middle: a key whose value is null (a comma split free text in a
    flow mapping) or text with unbalanced parentheses."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v is None and k not in ("rows", "crs"):
                found.append(f"{path}/{k}: null value, so the text before it was cut at a comma")
            found += broken_values(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += broken_values(v, f"{path}[{i}]")
    elif isinstance(obj, str) and (obj.count("(") != obj.count(")") or obj.count("（") != obj.count("）")):
        found.append(f"{path}: unbalanced parentheses: {obj[:40]}")
    return found


def frontmatter_problems(refs):
    """Problems in the frontmatter of the dataset references under `refs`."""
    problems, fms = [], {}
    files = sorted(f for f in refs.rglob("*.md") if f.name != "index.md")
    for f in files:
        rel = f.relative_to(refs)
        head = f.read_text().split("---\n", 2)[1] if f.read_text().startswith("---\n") else ""
        for line in head.splitlines():
            if FLOW.match(line):
                problems.append(f"{rel}: write collections in block style, not {{...}} or [...] (a comma or colon in free text breaks flow style): {line.strip()[:50]}")
                break
        try:
            fm = read_frontmatter(f)
        except yaml.YAMLError as e:
            problems.append(f"{rel}: frontmatter is not valid YAML ({str(e).splitlines()[0]})")
            continue
        if fm is None:
            problems.append(f"{rel}: no YAML frontmatter")
            continue
        fms[rel] = fm
        for item in broken_values({k: fm[k] for k in ("tables", "operations") if k in fm}):
            problems.append(f"{rel}: {item}")
        kind = fm.get("kind")
        if kind not in REQUIRED:
            problems.append(f"{rel}: kind must be one of {', '.join(REQUIRED)}")
            continue
        for key in REQUIRED[kind]:
            if key not in fm:
                problems.append(f"{rel}: missing {key}")
        for op in fm.get("operations", []):
            for key in ("name", "method", "path", "returns"):
                if key not in op:
                    problems.append(f"{rel}: operation {op.get('name', '?')} is missing {key}")
        for t in fm.get("tables", []):
            for key in ("name", "read", "grain", "id"):
                if key not in t:
                    problems.append(f"{rel}: table {t.get('name', '?')} is missing {key}")
            if not isinstance(t.get("id", []), list):
                problems.append(f"{rel}: table {t.get('name', '?')}: id must be a list")
            for c in t.get("columns", []):
                if not {"name", "type", "meaning"} <= set(c):
                    problems.append(f"{rel}: table {t.get('name', '?')}: a column needs name, type and meaning")
            for k in t.get("join_keys", []):
                if not {"column", "type", "meaning"} <= set(k):
                    problems.append(f"{rel}: table {t.get('name', '?')}: a join key needs column, type and meaning")
            for k in t.get("no_key", []):
                if not {"name", "note"} <= set(k):
                    problems.append(f"{rel}: table {t.get('name', '?')}: no_key needs name and note")
    short = {fm["id"].split("/")[-1]: fm for fm in fms.values() if "id" in fm}
    for rel, fm in fms.items():
        for t in fm.get("tables", []):
            for k in t.get("join_keys", []):
                for target in k.get("joins", []):
                    m = JOINS.match(str(target))
                    if not m:
                        continue
                    ds, table = m.group(1), m.group(2)
                    other = short.get(ds) if ds else fm
                    if other is None:
                        problems.append(f"{rel}: joins {target}: no dataset {ds}")
                    elif table != "*" and table not in {x["name"] for x in other.get("tables", [])}:
                        problems.append(f"{rel}: joins {target}: no table {table}")
                    elif table != "*":
                        column = target[m.end():].split(" (")[0]
                        theirs = column_type(other, table, column)
                        if theirs and k.get("type") and theirs.lower() != k["type"].lower() and "cast" not in k:
                            problems.append(f"{rel}: joins {target}: type {k['type']} vs {theirs}; say how to cast in `cast`")
    return problems


def cross_skill_problems(root, skills):
    problems = []
    for s in skills:
        others = [o for o in skills if o not in (s, "dataset-discovery")]
        for f in (root / s).rglob("*"):
            if not f.is_file() or f.suffix not in {".md", ".py"}:
                continue
            text = f.read_text()
            rel = f.relative_to(root)
            if re.search(r"\.\./(?!\.)[a-z]", text) and f.suffix == ".md":
                for m in re.finditer(r"\(?\.\./[a-z][\w-]*/", text):
                    if not m.group(0).strip("(").startswith("../references"):
                        problems.append(f"{rel}: relative path to another directory {m.group(0)}")
            if "parents[2]" in text:
                problems.append(f"{rel}: parents[2]")
            for o in others:
                if re.search(rf"(?<![\w-]){re.escape(o)}(?![\w-])", text):
                    problems.append(f"{rel}: names the skill {o}")
    return problems


def copy_problems(root, copies):
    problems = []
    for name, dirs in copies.items():
        first = root / dirs[0] / "scripts" / name
        for d in dirs[1:]:
            other = root / d / "scripts" / name
            if not first.exists() or not other.exists() or not filecmp.cmp(first, other, shallow=False):
                problems.append(f"copies differ or are missing: {first.relative_to(root)} / {other.relative_to(root)}")
    return problems


def style_problems(root):
    """Bold (**x** or __x__) and the em dash, outside code spans and fenced code blocks."""
    problems = []
    for f in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in f.relative_to(root).parts):
            continue
        text = re.sub(r"```.*?```", "", f.read_text(), flags=re.S)
        text = re.sub(r"`[^`\n]*`", "", text)
        for line in text.splitlines():
            if re.search(r"\*\*\S[^*]*\*\*|(?<!\w)__\S[^_]*__(?!\w)", line) or "\u2014" in line:
                problems.append(f"{f.relative_to(root)}: bold or em dash: {line.strip()[:50]}")
                break
    return problems


def script_test_problems(root):
    problems = []
    for f in sorted(root.glob("*/scripts/*.py")):
        if not f.name.startswith("test_") and not (f.parent / f"test_{f.name}").exists():
            problems.append(f"{f.relative_to(root)}: no test_{f.name} beside it")
    return problems


def todo_problems(root):
    """TODO.md against the files. Lines: '- stage (done / all)', '  - [x] `skill`: ...', then references
    ('    - [x] `references/x.md`', several on a line allowed) and, under a catalogue README, '      - [x] `cat/f.md`'."""
    problems, stages, listed, skill, catalog = [], [], {}, None, None
    for line in (root / "TODO.md").read_text().splitlines():
        m = re.match(r"^- (.+) \((\d+) / (\d+)\)$", line)
        if m:
            stages.append([m.group(1), int(m.group(2)), int(m.group(3)), 0, 0])
            continue
        m = re.match(r"^  - \[( |x)\] `([\w-]+)`", line)
        if m and stages:
            done, skill, catalog = m.group(1) == "x", m.group(2), None
            stages[-1][3] += done
            stages[-1][4] += 1
            f = root / skill / "SKILL.md"
            real = f.exists() and f.read_text().strip() != ""
            if done != real:
                problems.append(f"TODO.md: skill {skill} is {'checked' if done else 'unchecked'} but has "
                                f"{'a' if real else 'no'} SKILL.md with content")
            listed.setdefault(skill, set())
            continue
        m = re.match(r"^( {4}| {6})- \[( |x)\] (.*)$", line)
        if not (m and skill):
            continue
        done = m.group(2) == "x"
        for n in re.findall(r"`([\w./-]+\.md)`", m.group(3)):
            if len(m.group(1)) == 6 and catalog and "/" not in n:
                rel = f"{catalog}/{n}"
            else:
                rel = n if n.startswith("references/") else f"references/{n}"
                if n.endswith("/README.md"):
                    catalog = str(Path(rel).parent)
            f = root / skill / rel
            listed[skill].add(f)
            if done != f.exists():
                problems.append(f"TODO.md: {skill}/{rel} is {'checked' if done else 'unchecked'} but exists={f.exists()}")
    for name, says_done, says_all, done, total in stages:
        if (says_done, says_all) != (done, total):
            problems.append(f"TODO.md: stage {name} says ({says_done} / {says_all}), counted ({done} / {total})")
    for d in sorted(p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").exists()):
        if d.name not in listed:
            problems.append(f"TODO.md: skill {d.name} is not listed")
            continue
        for f in sorted((d / "references").rglob("*.md")) if (d / "references").exists() else []:
            if f not in listed[d.name]:
                problems.append(f"TODO.md: {f.relative_to(root)} exists but is not in TODO")
    return problems


PACKAGES = {"sklearn": "scikit-learn", "yaml": "pyyaml", "PIL": "pillow", "skimage": "scikit-image"}
BRINGS = {"scikit-learn": {"numpy", "scipy", "joblib"}, "scipy": {"numpy"}, "rasterio": {"numpy"},
          "pandas": {"numpy"}, "shapely": {"numpy"}, "pyproj": set(), "statsmodels": {"numpy", "scipy", "pandas"},
          "geopandas": {"numpy", "pandas", "shapely", "pyproj"}, "esda": {"numpy", "scipy", "libpysal"}}


def _imports(path, top_only=False):
    """Top-level module names imported in the file, except inside a try block (optional imports).
    With top_only, only the imports at module level (not those inside functions)."""
    import ast
    tree = ast.parse(path.read_text())
    nodes = tree.body if top_only else list(ast.walk(tree))
    skip = {id(n) for node in ast.walk(tree) if isinstance(node, ast.Try) for sub in node.body for n in ast.walk(sub)}
    found = set()
    for node in nodes:
        if id(node) in skip:
            continue
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module.split(".")[0])
    return found


def test_command_problems(root):
    """The uvx line at the top of each test must bring every third-party package that the test uses, and that
    the scripts beside it use when imported (module level) or, if the test runs them as commands, at all."""
    problems = []
    for t in sorted(root.glob("*/scripts/test_*.py")):
        text = t.read_text()
        first = text.split("\n", 1)[0]
        if "uvx" not in first:
            problems.append(f"{t.relative_to(root)}: no uvx command on its first line")
            continue
        local = {p.stem for p in t.parent.glob("*.py")}
        mods = _imports(t)
        runs_scripts = "subprocess" in mods
        for m in sorted(local):
            if m in mods or (runs_scripts and f"{m}.py" in text):
                mods |= _imports(t.parent / f"{m}.py", top_only=not runs_scripts)
        wanted = {PACKAGES.get(m, m) for m in mods - local - set(sys.stdlib_module_names) - {"pytest"}}
        have = {x.lower() for x in re.findall(r"(?:--with|--from)\s+'?([A-Za-z0-9_.-]+)", first)}
        have |= {b for h in list(have) for b in BRINGS.get(h, set())}
        for pkg in sorted(wanted):
            if pkg.lower() not in have:
                problems.append(f"{t.relative_to(root)}: the command lacks {pkg}")
    return problems


def main():
    root = Path(__file__).parent
    skills = sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
    COPIES = {
        "score_folds.py": ["eda-and-baseline", "cross-validation-design"],
        "test_score_folds.py": ["eda-and-baseline", "cross-validation-design"],
        "knn_neighbors.py": ["anomaly-detection", "clustering-analysis"],
        "test_knn_neighbors.py": ["anomaly-detection", "clustering-analysis"],
        "compare_models.py": ["spatial-data-modeling", "leakage-audit", "model-explanation"],
        "contiguity.py": ["spatial-autocorrelation", "spatial-weights-design"],
        "test_contiguity.py": ["spatial-autocorrelation", "spatial-weights-design"],
        "test_compare_models.py": ["spatial-data-modeling", "leakage-audit", "model-explanation"],
    }
    problems = cross_skill_problems(root, skills) + copy_problems(root, COPIES)
    problems += frontmatter_problems(root / "dataset-discovery" / "references")
    problems += style_problems(root) + script_test_problems(root) + todo_problems(root) + test_command_problems(root)
    print("\n".join(problems) or "ok")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
