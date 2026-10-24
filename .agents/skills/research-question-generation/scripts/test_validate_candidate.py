# uvx --with pytest --with pyyaml python -m pytest -q .agents/skills/research-question-generation/scripts/test_validate_candidate.py
"""Known-answer and mutation checks for proposal gates."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("validate_candidate.py")
SPEC = importlib.util.spec_from_file_location("proposal_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def context():
    return MODULE.load_catalog(ROOT), MODULE.load_history(ROOT)


@pytest.fixture
def candidate():
    return {
        "mode": "exploration",
        "question": "東京23区でアンダーパス区間を通れないと仮定すると、洪水向け指定緊急避難場所への徒歩経路が大きく悪化する高齢者の多い1kmメッシュはどこか？",
        "decision_use": "自治体が代替避難経路の現地確認を優先する区域を選ぶ",
        "target_quantity": "閉鎖シナリオ前後の徒歩道のりの増分と到達不能人数",
        "unit": "2020年国勢調査の1kmメッシュ",
        "time_alignment": "人口2020、アンダーパス2025、道路と避難場所2026の差を明示",
        "datasets": [
            "yuiseki/mlit-underpass", "yuiseki/gsi-evacuation-sites-jp",
            "yuiseki/estat-census-mesh-2020", "yuiseki/osm-japan-src-2026-08",
            "yuiseki/jp-admin-2026-09",
        ],
        "joins": [
            {"left": "yuiseki/mlit-underpass", "right": "yuiseki/osm-japan-src-2026-08", "how": "projected nearest road", "why": "閉鎖する候補の道路を特定"},
            {"left": "yuiseki/gsi-evacuation-sites-jp", "right": "yuiseki/osm-japan-src-2026-08", "how": "network snap", "why": "避難場所までの道のり"},
            {"left": "yuiseki/estat-census-mesh-2020", "right": "yuiseki/osm-japan-src-2026-08", "how": "mesh representative points", "why": "起点と需要"},
            {"left": "yuiseki/jp-admin-2026-09", "right": "yuiseki/estat-census-mesh-2020", "how": "spatial containment", "why": "対象範囲"},
        ],
        "required_variables": [
            {"dataset": "yuiseki/mlit-underpass", "table": "underpass", "column": "geometry"},
            {"dataset": "yuiseki/gsi-evacuation-sites-jp", "table": "sites", "column": "flood"},
            {"dataset": "yuiseki/estat-census-mesh-2020", "table": "T001140", "column": "KEY_CODE"},
            {"dataset": "yuiseki/estat-census-mesh-2020", "table": "T001140", "column": "T001140019",
             "evidence_file": "projects/tokyo-mainland-elderly-transit-gaps/scripts/analyze.py"},
            {"dataset": "yuiseki/osm-japan-src-2026-08", "table": "planet_osm_line", "column": "osm_id"},
            {"dataset": "yuiseki/osm-japan-src-2026-08", "table": "planet_osm_line", "column": "way",
             "evidence_file": "projects/tokyo-mainland-elderly-transit-gaps/scripts/analyze.py"},
            {"dataset": "yuiseki/jp-admin-2026-09", "table": "municipalities", "column": "geometry"},
        ],
        "methodological_decisions": ["歩行可能道と閉鎖区間の対応", "メッシュ内人口位置", "到達不能の扱い"],
        "failure_modes": ["車道アンダーパスと歩道の違い", "道路網の立体交差", "秘匿年齢と時点差"],
        "robustness_checks": ["閉鎖区間の長さ", "メッシュ代表点", "スナップ距離"],
        "simplest_solver": {"method": "閉鎖前の最寄り避難場所までの直線距離", "why_insufficient": "閉鎖による迂回と非連結を表せない"},
        "unknowns": ["実際の冠水と閉鎖", "避難場所の収容能力", "歩道の通行可否"],
        "novelty": {"closest_task": 37, "difference_dimension": "stress_scenario", "substantive_difference": "既存の遠さではなく道路閉鎖による到達性の変化を測る"},
        "prediction": {"main_result": "一部の河川沿いで迂回が大きい", "difficulty": "点を道路区間へ対応", "fragile_assumption": "閉鎖を歩道にも適用", "needed_capabilities": ["network routing", "sensitivity audit"]},
        "rubric": ["閉鎖前後を同じ道路網で比較", "非連結を無限の距離として足さない", "別の区間対応でも候補が残るか"],
    }


def test_known_good_reaches_critic_not_auto_adoption(candidate, context):
    catalog, history = context
    result = MODULE.evaluate(candidate, catalog, history)
    assert result["status"] == "critic_review"
    assert result["reasons"] == []


def test_tree_cover_task_card_candidate_is_reviewable(context):
    path = ROOT / "evals/curriculum/proposals/2026-10-24-tokyo-tree-cover-presence.json"
    proposal = json.loads(path.read_text())
    result = MODULE.evaluate(proposal, *context)
    assert result == {"status": "critic_review", "reasons": []}


def test_trivial_single_table_maximum_is_rejected(candidate, context):
    bad = copy.deepcopy(candidate)
    bad["question"] = "東京都で病院が一番多い区はどこ？"
    bad["datasets"] = ["yuiseki/osm-japan-src-2026-08"]
    bad["joins"] = []
    bad["simplest_solver"] = {"method": "GROUP BY と最大値", "why_insufficient": ""}
    result = MODULE.evaluate(bad, *context)
    assert "no_integration" in result["reasons"]
    assert "trivial_solver" in result["reasons"]


def test_impossible_operating_frequency_is_rejected(candidate, context):
    bad = copy.deepcopy(candidate)
    bad["question"] = "バス停の運行頻度の因果効果で移動が改善したか？"
    bad["datasets"] = ["yuiseki/ksj-p11-bus-stop-jp"]
    bad["required_variables"] = [{"dataset": "yuiseki/ksj-p11-bus-stop-jp", "table": "bus_stops", "column": "operating_frequency"}]
    bad["claim_type"] = "causal"
    result = MODULE.evaluate(bad, *context)
    assert any(reason.startswith("unsupported_variable:") for reason in result["reasons"])
    assert "causal_design_missing" in result["reasons"]


def test_claimed_evidence_must_actually_contain_the_column(candidate, context):
    bad = copy.deepcopy(candidate)
    bad["required_variables"][0] = {"dataset": "yuiseki/mlit-underpass", "table": "underpass",
                                    "column": "operating_frequency", "evidence_file": "README.md"}
    assert any(r.startswith("unsupported_variable:") for r in MODULE.evaluate(bad, *context)["reasons"])


def test_reference_saying_a_key_does_not_exist_is_not_column_evidence(candidate, context):
    bad = copy.deepcopy(candidate)
    bad["required_variables"][-1]["column"] = "osm_id"
    assert any(r.startswith("unsupported_variable:") for r in MODULE.evaluate(bad, *context)["reasons"])


def test_missing_joins_is_rejected_without_crashing(candidate, context):
    bad = copy.deepcopy(candidate)
    del bad["joins"]
    assert "missing:joins" in MODULE.evaluate(bad, *context)["reasons"]


@pytest.mark.parametrize("field,value", [
    ("datasets", ["yuiseki/mlit-underpass", {}]),
    ("joins", "not a list"),
    ("required_variables", ["not an object"]),
    ("novelty", "not an object"),
    ("simplest_solver", ["not an object"]),
])
def test_malformed_schema_rejects_instead_of_raising(candidate, context, field, value):
    bad = copy.deepcopy(candidate)
    bad[field] = value
    assert MODULE.evaluate(bad, *context)["status"] == "reject"


def test_geography_only_rewording_is_rejected(candidate, context):
    bad = copy.deepcopy(candidate)
    bad["question"] = "大阪市で、洪水のときに使える指定緊急避難場所まで歩く距離が長く、高齢者が多い1kmメッシュはどこ？"
    bad["novelty"] = {"closest_task": 37, "difference_dimension": "geography_only", "substantive_difference": "大阪市に変更"}
    result = MODULE.evaluate(bad, *context)
    assert "geography_only" in result["reasons"]
    assert any(reason.startswith("near_duplicate:") for reason in result["reasons"])


def test_method_first_without_world_question_is_rejected(candidate, context):
    bad = copy.deepcopy(candidate)
    bad["question"] = "SDEを使って何か分析する"
    assert "method_first" in MODULE.evaluate(bad, *context)["reasons"]


def test_mutation_disabling_duplicate_gate_lets_bad_candidate_through(candidate, context, monkeypatch):
    bad = copy.deepcopy(candidate)
    bad["question"] = "大阪市で、洪水のときに使える指定緊急避難場所まで歩く距離が長く、高齢者が多い1kmメッシュはどこ？"
    bad["novelty"] = {"closest_task": 37, "difference_dimension": "stress_scenario", "substantive_difference": "閉鎖時の変化を測る"}
    assert any(r.startswith("near_duplicate:") for r in MODULE.evaluate(bad, *context)["reasons"])
    monkeypatch.setattr(MODULE, "duplicate_reason", lambda question, history: None)
    assert MODULE.evaluate(bad, *context)["status"] == "critic_review"
