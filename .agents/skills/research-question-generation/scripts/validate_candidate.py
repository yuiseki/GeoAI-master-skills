"""Check proposal evidence and obvious rejection gates, not research merit.

Usage: uvx --with pyyaml python .agents/skills/research-question-generation/scripts/validate_candidate.py candidate.json
The command reads the repository's dataset references and task history. It never edits them.
"""

import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
REQUIRED = (
    "mode", "question", "decision_use", "target_quantity", "unit", "time_alignment",
    "datasets", "joins", "required_variables", "methodological_decisions",
    "failure_modes", "robustness_checks", "simplest_solver", "unknowns",
    "novelty", "prediction", "rubric",
)
GEOGRAPHY = re.compile(r"東京(?:都|23区)?|大阪(?:府|市)?|長野県|多摩地域|日本全国|本土")
METHOD_FIRST = re.compile(r"(?:SDE|GWR|MGWR|LISA|Moran|機械学習|回帰分析).{0,12}(?:使って|用いて).{0,12}(?:何か|分析する)", re.I)
TRIVIAL = re.compile(r"(?:一番多い|最も多い|最大|最小|最多|GROUP BY)", re.I)


def load_catalog(root=ROOT):
    """Read machine-readable inventories; retain prose for explicitly documented columns."""
    refs = root / ".agents/skills/dataset-discovery/references"
    catalog = {}
    for path in refs.rglob("*.md"):
        content = path.read_text()
        if not content.startswith("---\n"):
            continue
        schema_text = content.split("---\n", 2)[1]
        front = yaml.safe_load(schema_text)
        if not isinstance(front, dict) or front.get("kind") != "dataset":
            continue
        tables, aliases = {}, {}
        for table in front.get("tables", []):
            names = set(table.get("id", []))
            names.update(col["name"] for col in table.get("columns", []) if "name" in col)
            names.update(col["column"] for col in table.get("join_keys", []) if "column" in col)
            tables[table["name"]] = names
            aliases[table["name"]] = {
                name for col in table.get("columns", []) if "同じ形" in col.get("meaning", "")
                for name in re.findall(r"[a-z][a-z_]+", col["meaning"])
            }
        catalog[front["id"]] = {"tables": tables, "text": content, "schema_text": schema_text,
                                  "aliases": aliases,
                                  "reference": str(path.relative_to(root)),
                                  "root": root,
                                  "revision": front.get("card_revision"), "coverage": front.get("spatial_coverage"),
                                  "time": front.get("temporal_coverage"), "crs": front.get("crs")}
    return catalog


def load_history(root=ROOT):
    text = (root / "evals/tasks/hard-tasks.md").read_text()
    tasks = []
    for match in re.finditer(r"^## 課題 (\d+):[^\n]*\n(.*?)(?=^## 課題 |\Z)", text, re.M | re.S):
        question = re.search(r"^問い: (.+)$", match.group(2), re.M)
        if question:
            tasks.append((int(match.group(1)), question.group(1)))
    return tasks


def normalize_question(question):
    question = unicodedata.normalize("NFKC", question)
    question = GEOGRAPHY.sub("地域", question)
    return re.sub(r"[\s、。・,.?!？!（）()]", "", question).lower()


def duplicate_reason(question, history):
    """Conservative surface-form proxy; a critic still checks conceptual duplicates."""
    normalized = normalize_question(question)
    if not normalized:
        return None
    close = [(SequenceMatcher(None, normalized, normalize_question(old)).ratio(), number)
             for number, old in history]
    if not close:
        return None
    similarity, number = max(close)
    return f"near_duplicate:{number}" if similarity >= 0.82 else None


def _filled(value):
    return bool(value.strip()) if isinstance(value, str) else bool(value)


def evaluate(candidate, catalog, history):
    """Return hard-gate reasons. Passing only permits substantive critic review."""
    reasons = []
    if not isinstance(candidate, dict):
        return {"status": "reject", "reasons": ["invalid_schema"]}
    for field in REQUIRED:
        if field != "joins" and not _filled(candidate.get(field)):
            reasons.append(f"missing:{field}")
    if "joins" not in candidate:
        reasons.append("missing:joins")
    if reasons:
        return {"status": "reject", "reasons": reasons}
    if not isinstance(candidate["question"], str):
        return {"status": "reject", "reasons": ["invalid_question"]}
    if not isinstance(candidate["datasets"], list) or not all(
            isinstance(dataset, str) and dataset for dataset in candidate["datasets"]):
        return {"status": "reject", "reasons": ["invalid_datasets"]}
    if not isinstance(candidate["joins"], list) or not all(
            isinstance(join, dict) for join in candidate["joins"]):
        return {"status": "reject", "reasons": ["invalid_joins"]}
    if not isinstance(candidate["required_variables"], list) or not all(
            isinstance(variable, dict) for variable in candidate["required_variables"]):
        return {"status": "reject", "reasons": ["invalid_required_variables"]}
    if candidate["mode"] not in ("exploration", "digging"):
        reasons.append("invalid_mode")
    if candidate["mode"] == "digging" and not candidate.get("history_anchor"):
        reasons.append("digging_without_observation")
    question = candidate["question"]
    if METHOD_FIRST.search(question) or ("何か分析" in question and "使って" in question):
        reasons.append("method_first")
    duplicate = duplicate_reason(question, history)
    if duplicate:
        reasons.append(duplicate)

    dataset_ids = candidate["datasets"]
    ids = set(dataset_ids)
    if len(ids) != len(dataset_ids):
        reasons.append("duplicate_dataset")
    for dataset in ids:
        if dataset not in catalog:
            reasons.append(f"unknown_dataset:{dataset}")
    joins = candidate["joins"]
    if len(ids) < 2 or not joins:
        reasons.append("no_integration")
    else:
        adjacency = {dataset: set() for dataset in ids}
        for join in joins:
            left, right = join.get("left"), join.get("right")
            if left not in ids or right not in ids or not join.get("how") or not join.get("why"):
                reasons.append("invalid_join")
                continue
            adjacency[left].add(right)
            adjacency[right].add(left)
        seen = set()
        pending = [dataset_ids[0]]
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(adjacency[node] - seen)
        if seen != ids:
            reasons.append("disconnected_sources")

    for variable in candidate["required_variables"]:
        dataset = variable.get("dataset")
        table = variable.get("table")
        column = variable.get("column")
        if dataset not in ids or dataset not in catalog or table not in catalog[dataset]["tables"]:
            reasons.append(f"unsupported_variable:{dataset}.{table}.{column}")
            continue
        documented = column in catalog[dataset]["tables"][table]
        # Sibling columns explicitly described in a documented column's meaning.
        documented |= column in catalog[dataset]["aliases"][table]
        evidence_file = variable.get("evidence_file")
        if not documented and evidence_file:
            candidate_path = (catalog[dataset]["root"] / evidence_file).resolve()
            if candidate_path.is_relative_to(catalog[dataset]["root"].resolve()) and candidate_path.is_file():
                documented = bool(re.search(rf"(?<![\w]){re.escape(column)}(?![\w])", candidate_path.read_text()))
        if not documented:
            reasons.append(f"unsupported_variable:{dataset}.{table}.{column}")

    solver = candidate["simplest_solver"]
    if not isinstance(solver, dict) or not solver.get("why_insufficient"):
        reasons.append("trivial_solver")
    if TRIVIAL.search(question) and len(ids) < 2:
        if "trivial_solver" not in reasons:
            reasons.append("trivial_solver")
    if len(candidate["methodological_decisions"]) < 2 or not candidate["failure_modes"] or not candidate["robustness_checks"]:
        reasons.append("insufficient_methodological_depth")
    novelty = candidate["novelty"]
    if not isinstance(novelty, dict) or novelty.get("difference_dimension") in (None, "geography_only", "renaming_only"):
        reasons.append("geography_only")
    if not isinstance(novelty, dict) or not novelty.get("substantive_difference"):
        reasons.append("novelty_unexplained")
    if candidate.get("claim_type") == "causal" or re.search(r"因果効果|の効果で", question):
        design = candidate.get("causal_design", {})
        if not isinstance(design, dict) or not all(design.get(k) for k in (
                "treatment", "outcome", "estimand", "timing", "identification_assumption")):
            reasons.append("causal_design_missing")
    if not candidate["decision_use"] or not candidate["unknowns"] or len(candidate["rubric"]) < 2:
        reasons.append("not_evaluable")
    return {"status": "reject" if reasons else "critic_review", "reasons": list(dict.fromkeys(reasons))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="JSON candidate proposal")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text())
    result = evaluate(candidate, load_catalog(args.repo_root), load_history(args.repo_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["status"] == "reject" else 0)


if __name__ == "__main__":
    main()
