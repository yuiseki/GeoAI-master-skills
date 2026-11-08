"""uvx --with pyyaml --with pytest pytest -q test_trigger.py"""

import json
from pathlib import Path

import pytest

from trigger import judge, load_cases, prompt_problems, reads

HERE = Path(__file__).parent
SKILLS = HERE.parent / ".agents" / "skills"


def ev(tool, **inp):
    return json.dumps({"type": "tool_use", "part": {"tool": tool, "state": {"status": "completed", "input": inp}}})


def test_reads_takes_read_calls_and_files_named_in_shell_commands():
    log = "\n".join([
        ev("read", filePath="/work/.agents/skills/spatial-gnn/SKILL.md"),
        ev("read", filePath="/work/.agents/skills/spatial-gnn/references/dcrnn.md"),
        ev("bash", command="cat /work/.agents/skills/image-segmentation/references/training.md | head"),
        ev("bash", command="ls /work/.agents/skills/trajectory-prediction/references"),   # a listing is not a read
        ev("read", filePath="/work/AGENTS.md"),
        '{"type":"text","part":{"text":"spatial-interpolation/SKILL.md"}}',              # words are not reads
        "not json",
    ])
    assert reads(log) == {"spatial-gnn", "spatial-gnn/references/dcrnn.md",
                          "image-segmentation", "image-segmentation/references/training.md"}


def test_reading_a_reference_counts_as_reading_its_skill():
    log = ev("read", filePath="/work/.agents/skills/spatial-gnn/references/graph.md")
    assert reads(log) == {"spatial-gnn", "spatial-gnn/references/graph.md"}


def test_judge():
    case = {"expect": ["spatial-gnn", "spatial-gnn/references/dcrnn.md"], "forbid": ["image-segmentation"]}
    assert judge(case, {"spatial-gnn", "spatial-gnn/references/dcrnn.md"}, exit_code=0)["verdict"] == "PASS"
    r = judge(case, {"spatial-gnn"}, exit_code=0)
    assert r["verdict"] == "FAIL" and r["missing"] == ["spatial-gnn/references/dcrnn.md"]
    r = judge(case, {"spatial-gnn", "spatial-gnn/references/dcrnn.md", "image-segmentation"}, exit_code=0)
    assert r["verdict"] == "FAIL" and r["forbidden"] == ["image-segmentation"]
    # a run that failed is not graded; a run cut off by the time limit (124) is graded on what it read
    assert judge(case, {"spatial-gnn"}, exit_code=1)["verdict"] == "ERROR"
    assert judge(case, set(), exit_code=0, error_event=True)["verdict"] == "ERROR"
    assert judge(case, {"spatial-gnn", "spatial-gnn/references/dcrnn.md"}, exit_code=124)["verdict"] == "PASS"


def test_a_prompt_must_not_name_a_skill_or_a_reference():
    names = {"spatial-gnn", "dcrnn.md"}
    assert prompt_problems({"id": "x", "prompt": "道路の速度を当てたい"}, names) == []
    assert prompt_problems({"id": "x", "prompt": "spatial-gnn で当てたい"}, names) == ["x names spatial-gnn"]
    assert prompt_problems({"id": "x", "prompt": "dcrnn.md を読んで"}, names) == ["x names dcrnn.md"]


def test_the_cases_name_only_skills_and_references_that_exist_and_hide_them_from_the_prompt():
    cases = load_cases(HERE / "trigger_cases.yaml")
    assert {c["kind"] for c in cases} == {"explicit", "implicit", "scope", "negative"}
    assert len({c["id"] for c in cases}) == len(cases)
    names = {d.name for d in SKILLS.iterdir() if d.is_dir()} | {f.name for f in SKILLS.glob("*/references/*.md")}
    for c in cases:
        for item in c.get("expect", []) + c.get("forbid", []):
            assert (SKILLS / (item if "/" in item else item + "/SKILL.md")).exists(), (c["id"], item)
        assert prompt_problems(c, names) == []
        if c["kind"] == "negative":
            assert not c.get("expect") and c.get("forbid")
        else:
            assert c.get("expect")


def test_the_skill_tool_counts_as_reading_the_skill():
    # OpenCode loads a SKILL.md with its own skill tool (seen in the i2-taxi run, 2026-11-09)
    assert reads(ev("skill", name="trajectory-prediction")) == {"trajectory-prediction"}
