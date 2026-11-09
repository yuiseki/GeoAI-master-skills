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
    tuning = load_cases(HERE / "trigger_cases.yaml")
    held = (load_cases(HERE / "trigger_holdout.yaml") + load_cases(HERE / "trigger_holdout2.yaml") +
            load_cases(HERE / "trigger_holdout3.yaml"))
    assert {c["kind"] for c in tuning} == {"explicit", "implicit", "scope", "negative"}
    cases = tuning + held
    assert len({c["id"] for c in cases}) == len(cases)       # the two sets never share an id
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


def test_repeats_are_graded_per_run_and_summed_per_case(tmp_path):
    from trigger import grade
    case = {"id": "c", "kind": "implicit", "expect": ["spatial-gnn"]}
    for r, (tool_path, code) in enumerate([("spatial-gnn/SKILL.md", 0), ("image-segmentation/SKILL.md", 0),
                                           ("spatial-gnn/SKILL.md", 1)], 1):
        d = tmp_path / "c" / f"r{r}"
        d.mkdir(parents=True)
        (d / "log").write_text(ev("read", filePath=f"/work/.agents/skills/{tool_path}"))
        (d / "exit").write_text(f"{code}\n")
    rows, cases = grade(tmp_path, [case])
    assert [r[2] for r in rows] == ["PASS", "FAIL", "ERROR"]
    assert cases == [["c", "implicit", "1", "2", "1"]]          # id, kind, passed, graded, errors
    assert (tmp_path / "cases.tsv").read_text().splitlines()[1] == "c\timplicit\t1\t2\t1"


def test_a_run_with_no_event_at_all_is_an_error_not_a_grade():
    """The provider can hang until the time limit without sending one event. The log is then empty: the agent never
    saw the request, so the run says nothing about the skills (and a negative case would pass for free)."""
    from trigger import silent
    assert silent("")
    assert silent("not json\n")
    assert not silent(ev("read", filePath="/work/README.md"))
    case = {"id": "n", "kind": "negative", "forbid": ["spatial-gnn"]}
    assert judge(case, set(), exit_code=124, error_event=False, silent=True)["verdict"] == "ERROR"


def test_retry_errors_sets_the_failed_run_aside_and_keeps_the_graded_ones(tmp_path):
    from trigger import _needs_run
    case = {"id": "c", "kind": "implicit", "expect": ["spatial-gnn"]}
    ok, empty = tmp_path / "c" / "r1", tmp_path / "c" / "r2"
    for d in (ok, empty):
        d.mkdir(parents=True)
        (d / "exit").write_text("124\n")
    (ok / "log").write_text(ev("read", filePath="/work/.agents/skills/spatial-gnn/SKILL.md"))
    (empty / "log").write_text("")
    assert not _needs_run(tmp_path, case, 1, retry_errors=True)
    assert not _needs_run(tmp_path, case, 2, retry_errors=False)
    assert _needs_run(tmp_path, case, 2, retry_errors=True)
    assert not empty.exists() and (tmp_path / "c" / "err" / "r2-1" / "exit").exists()   # kept, out of the grade
    assert _needs_run(tmp_path, case, 3, retry_errors=False)


def test_the_free_usage_limit_is_recognised_in_the_stderr_of_a_run():
    """OpenCode retries a provider's usage limit until the time limit and writes nothing to stdout; the reason is
    only in its stderr (seen 2026-11-09: 25 runs of 10 minutes each, all empty)."""
    from trigger import usage_limited
    err = ('level=ERROR message="stream error" error.error="AI_APICallError: Free usage limit reached. '
           'Free models work in OpenCode (https://opencode.ai); subscribe to OpenCode Go to keep going"')
    assert usage_limited(err)
    assert not usage_limited('level=INFO message="llm runtime selected"')
    assert not usage_limited('level=INFO message="rate limit headers" remaining=100')
    assert not usage_limited("")


def test_only_runs_the_named_cases_but_the_tables_keep_every_case(tmp_path):
    """--only once rewrote summary.tsv and cases.tsv with the one case it ran, dropping the others' rows."""
    import subprocess
    import sys
    for cid in ("e2-kriging", "n1-typo"):
        d = tmp_path / cid / "r1"
        d.mkdir(parents=True)
        (d / "log").write_text(ev("read", filePath="/work/README.md") + "\n")
        (d / "exit").write_text("0\n")
    subprocess.run([sys.executable, str(HERE / "trigger.py"), "judge", str(tmp_path), "--only", "n1-typo"], check=True)
    ids = [line.split("\t")[0] for line in (tmp_path / "cases.tsv").read_text().splitlines()[1:]]
    assert ids == ["e2-kriging", "n1-typo"]


def agy(tool, state="DONE", **params):
    return json.dumps({"event": "step_update", "step_update": {"step_index": 1, "state": state, "step_type": "tool",
                                                                "tool_name": tool, "tool_info": {"name": tool,
                                                                                                 "parameters": params}}})


def cx(command, kind="command_execution"):
    return json.dumps({"type": "item.completed", "item": {"id": "i", "type": kind, "command": command,
                                                          "exit_code": 0, "status": "completed"}})


def test_reads_takes_the_gemini_cli_s_file_tools_and_commands():
    """agy --output-format stream-json (seen 2026-11-09): read_file / view_file with Path, run_command with a
    command line. Listings (list_dir, find_by_name) are not reads."""
    log = "\n".join([
        json.dumps({"event": "init", "init": {"model": "gemini-3.8-flash-low"}}),
        agy("read_file", Path="/work/.agents/skills/spatial-gnn/SKILL.md", StartLine=1, EndLine=100),
        agy("view_file", AbsolutePath="/work/.agents/skills/spatial-gnn/references/dcrnn.md"),
        agy("run_command", CommandLine="sed -n 1,80p .agents/skills/point-pattern-analysis/references/ripley.md"),
        agy("list_dir", DirectoryPath="/work/.agents/skills/trajectory-prediction/references"),
        agy("read_file", state="ACTIVE", Path="/work/.agents/skills/image-segmentation/SKILL.md"),
    ])
    assert reads(log) == {"spatial-gnn", "spatial-gnn/references/dcrnn.md",
                          "point-pattern-analysis", "point-pattern-analysis/references/ripley.md"}


def test_reads_takes_codex_s_shell_commands():
    log = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "x"}),
        cx("/bin/bash -lc 'cat .agents/skills/spatial-gnn/SKILL.md'"),
        cx("/bin/bash -lc \"sed -n '1,120p' .agents/skills/spatial-gnn/references/dcrnn.md\""),
        cx("/bin/bash -lc 'ls .agents/skills/trajectory-prediction/references'"),
    ])
    assert reads(log) == {"spatial-gnn", "spatial-gnn/references/dcrnn.md"}


def test_a_failed_turn_or_run_is_an_error_event_in_each_format():
    from trigger import error_event
    assert error_event(json.dumps({"type": "turn.failed", "error": {"message": "unauthorized (401)"}}))
    assert not error_event(json.dumps({"type": "error", "message": "Reconnecting... 1/5"}) + "\n" + cx("cat x"))
    assert error_event(json.dumps({"event": "result", "result": {"status": "ERROR"}}))
    assert not error_event(json.dumps({"event": "result", "result": {"status": "SUCCESS"}}))
    assert error_event(json.dumps({"type": "error", "error": {"name": "APIError"}}))      # opencode


def test_each_agent_gets_its_runner_and_the_run_records_the_model(tmp_path):
    """The command for each agent, and the agent, model and effort written next to the log (results are only
    comparable within one model)."""
    from trigger import agent_command
    cmd, meta = agent_command("codex", None, None, tmp_path / "p.md", tmp_path / "w")
    assert cmd[0].endswith("run_codex_docker.sh") and cmd[-4:] == ["-m", "gpt-6-luna", "-c",
                                                                   "model_reasoning_effort=medium"]
    assert "--json" in cmd and meta == {"agent": "codex", "model": "gpt-6-luna", "effort": "medium"}
    cmd, meta = agent_command("gemini", None, None, tmp_path / "p.md", tmp_path / "w")
    assert cmd[0].endswith("run_gemini_docker.sh") and "--auth" in cmd
    assert meta == {"agent": "gemini", "model": "gemini-3.8-flash-low", "effort": ""}
    cmd, meta = agent_command("opencode", "opencode/glm-5.3-flash-free", None, tmp_path / "p.md", tmp_path / "w")
    assert cmd[0].endswith("run_opencode_docker.sh")
    assert meta == {"agent": "opencode", "model": "opencode/glm-5.3-flash-free", "effort": ""}
    with pytest.raises(ValueError):
        agent_command("gemini", None, "high", tmp_path / "p.md", tmp_path / "w")   # the effort is in the name


def test_a_manifest_that_differs_names_what_changed():
    """An OUT_DIR is one condition: resuming or retrying with another revision, cases, model, image, CLI, runner
    or time limit is refused, and the refusal says which."""
    from trigger import manifest_diff
    old = {"revision": "a" * 40, "cases_sha256": "c1", "agent": "gemini", "model": "gemini-3.8-flash-low",
           "effort": "", "image_id": "sha256:1", "cli_version": "1.3.5", "runner_sha256": "r1", "minutes": 10,
           "created": "2026-11-09T12:00:00+09:00"}
    assert manifest_diff(old, dict(old, created="2026-11-10T09:00:00+09:00")) == []     # the time is not a condition
    assert manifest_diff(old, dict(old, revision="b" * 40, cli_version="1.3.6")) == ["cli_version", "revision"]


def test_the_cases_are_read_from_the_pinned_revision_not_the_working_tree():
    from trigger import cases_at, load_cases
    import subprocess
    head = subprocess.run(["git", "-C", str(HERE.parent), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    first = subprocess.run(["git", "-C", str(HERE.parent), "log", "--format=%H", "--diff-filter=A", "--",
                            "evals/trigger_cases.yaml"], capture_output=True, text=True).stdout.split()[-1]
    assert [c["id"] for c in cases_at(head)] == [c["id"] for c in load_cases(HERE / "trigger_cases.yaml")]
    assert len(cases_at(first)) < len(cases_at(head))      # the first version had fewer cases


def test_shell_reads_through_brace_expansion_and_for_loops_count():
    """Seen with Codex on 2026-11-09: several SKILL.md at once, named only after the shell expands them."""
    log = "\n".join([
        cx("/bin/sh -lc 'for f in .agents/skills/{dataset-discovery,cross-validation-design}/SKILL.md; "
           "do echo \"### $f\"; cat \"$f\"; done'"),
        cx("/bin/sh -lc 'for s in leakage-audit eda-and-baseline; do echo \"### $s\"; "
           "cat .agents/skills/$s/SKILL.md; done'"),
        cx("/bin/sh -lc 'for s in spatial-gnn; do cat \".agents/skills/${s}/references/dcrnn.md\"; done'"),
        cx("/bin/sh -lc 'ls .agents/skills/{trajectory-prediction,causal-design}'"),     # a listing still is not
    ])
    assert reads(log) == {"dataset-discovery", "cross-validation-design", "leakage-audit", "eda-and-baseline",
                          "spatial-gnn", "spatial-gnn/references/dcrnn.md"}


FILES = [".agents/skills/point-pattern-analysis/SKILL.md",
         ".agents/skills/point-pattern-analysis/references/ripley.md",
         ".agents/skills/point-pattern-analysis/references/baselines.md",
         ".agents/skills/spatial-gnn/SKILL.md",
         ".agents/skills/spatial-gnn/references/dcrnn.md",
         ".agents/skills/spatial-gnn/references/graph.md"]


def test_a_glob_inside_one_skill_reads_the_files_it_matches_at_the_revision():
    """Seen with a Claude subagent on 2026-11-10: cat references/*.md read every reference of the skill."""
    log = "\n".join([
        cx("/bin/bash -lc 'cat .agents/skills/point-pattern-analysis/references/*.md'"),
        ev("bash", command="head -50 /work/.agents/skills/spatial-gnn/references/d?rnn.md"),
    ])
    assert reads(log, FILES) == {"point-pattern-analysis", "point-pattern-analysis/references/ripley.md",
                                 "point-pattern-analysis/references/baselines.md",
                                 "spatial-gnn", "spatial-gnn/references/dcrnn.md"}


def test_a_glob_that_lists_or_spans_skills_is_not_a_read():
    """ls of a glob only lists. A wildcard in the skill's name is a search across skills, like grep -r on the
    folder, and would otherwise count all 59 SKILL.md as read."""
    log = "\n".join([
        cx("/bin/bash -lc 'ls .agents/skills/spatial-gnn/references/*.md'"),
        cx("/bin/bash -lc 'grep -l DCRNN .agents/skills/*/SKILL.md'"),
        cx("/bin/bash -lc 'find .agents/skills/spatial-gnn -name \"*.md\"'"),
    ])
    assert reads(log, FILES) == set()


def test_without_the_file_list_a_glob_is_not_expanded():
    assert reads(cx("/bin/bash -lc 'cat .agents/skills/spatial-gnn/references/*.md'")) == set()


def test_grade_expands_globs_against_the_skill_files_at_the_pinned_revision(tmp_path):
    from trigger import _git, grade, skill_files
    head = _git("rev-parse", "HEAD").strip()
    assert ".agents/skills/spatial-gnn/references/dcrnn.md" in skill_files(head)
    case = {"id": "c", "kind": "implicit", "expect": ["spatial-gnn/references/dcrnn.md"]}
    d = tmp_path / "c" / "r1"
    d.mkdir(parents=True)
    (d / "log").write_text(cx("/bin/bash -lc 'cat .agents/skills/spatial-gnn/references/*.md'"))
    (d / "exit").write_text("0\n")
    assert [r[2] for r in grade(tmp_path, [case], skill_files(head))[0]] == ["PASS"]
    assert [r[2] for r in grade(tmp_path, [case])[0]] == ["FAIL"]
