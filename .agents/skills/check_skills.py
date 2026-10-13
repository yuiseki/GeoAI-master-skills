"""Check that every skill stands alone.

    python3 check_skills.py

1. No skill points at another skill's files (a relative path, or a script path built from parents[2]).
2. No skill names another skill, except dataset-discovery (the catalogue of dataset facts) and its own name.
3. A script shared by several skills is a copy; the copies must be identical.
4. Every dataset reference in dataset-discovery starts with YAML frontmatter that has the required keys,
   and every `joins` entry points at a dataset and table that exist (needs PyYAML).
"""

import filecmp
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is needed to check the dataset frontmatter: uvx --with pyyaml python check_skills.py")

COMMON = ["id", "description", "url", "license", "spatial_coverage", "temporal_coverage", "contents"]
JOINS = re.compile(r"^(?:([\w-]+):)?([\w*]+)\.")


def read_frontmatter(path):
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    return yaml.safe_load(text.split("---\n", 2)[1])


def frontmatter_problems(refs):
    """Problems in the frontmatter of the dataset references under `refs`."""
    problems, fms = [], {}
    files = sorted(refs.rglob("*.md"))
    for f in files:
        rel = f.relative_to(refs)
        try:
            fm = read_frontmatter(f)
        except yaml.YAMLError as e:
            problems.append(f"{rel}: frontmatter is not valid YAML ({str(e).splitlines()[0]})")
            continue
        if fm is None:
            problems.append(f"{rel}: no YAML frontmatter")
            continue
        fms[rel] = fm
        kind = fm.get("kind")
        if kind not in ("dataset", "catalog"):
            problems.append(f"{rel}: kind must be dataset or catalog")
            continue
        for key in COMMON + (["access"] if kind == "catalog" else ["tables"]):
            if key not in fm:
                problems.append(f"{rel}: missing {key}")
        for t in fm.get("tables", []):
            for key in ("name", "read", "grain", "id"):
                if key not in t:
                    problems.append(f"{rel}: table {t.get('name', '?')} is missing {key}")
            if not isinstance(t.get("id", []), list):
                problems.append(f"{rel}: table {t.get('name', '?')}: id must be a list")
            for c in t.get("columns", []):
                if not {"name", "meaning"} <= set(c):
                    problems.append(f"{rel}: table {t.get('name', '?')}: a column needs name and meaning")
            for k in t.get("join_keys", []):
                if not {"column", "meaning"} <= set(k):
                    problems.append(f"{rel}: table {t.get('name', '?')}: a join key needs column and meaning")
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
    }
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
    for name, dirs in COPIES.items():
        first = root / dirs[0] / "scripts" / name
        for d in dirs[1:]:
            other = root / d / "scripts" / name
            if not first.exists() or not other.exists() or not filecmp.cmp(first, other, shallow=False):
                problems.append(f"copies differ or are missing: {first.relative_to(root)} / {other.relative_to(root)}")
    problems += frontmatter_problems(root / "dataset-discovery" / "references")
    print("\n".join(problems) or "ok")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
