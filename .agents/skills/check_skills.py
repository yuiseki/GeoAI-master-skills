"""Check that every skill stands alone.

    python3 check_skills.py

1. No skill points at another skill's files (a relative path, or a script path built from parents[2]).
2. No skill names another skill, except dataset-discovery (the catalogue of dataset facts) and its own name.
3. A script shared by several skills is a copy; the copies must be identical.
"""

import filecmp
import re
import sys
from pathlib import Path

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
print("\n".join(problems) or "ok")
sys.exit(1 if problems else 0)
