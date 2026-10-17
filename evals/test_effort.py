"""Tests for effort.py: how much work a run took, read from the agent's own log."""

import json
import os

from effort import parse_agy, parse_codex, parse_opencode, run_effort

CODEX_LOG = """codex
まず確認します。
exec
/bin/sh -lc 'ls' in /work
 succeeded in 0ms:
a
exec
/bin/sh -lc 'python x.py' in /work
 exited 1 in 120ms:
Traceback
exec
/bin/sh -lc 'python y.py' in /work
 succeeded in 2.1s:
ok
tokens used
12,345
done
tokens used
60,071
done
"""


def agy_line(event, **body):
    return json.dumps({"event": event, event: body})


AGY_LOG = "\n".join([
    agy_line("init", model="gemini-3.8-flash-low"),
    agy_line("step_update", step_index=0, state="DONE", step_type="user_input"),
    agy_line("step_update", step_index=1, state="ACTIVE", step_type="tool"),
    agy_line("step_update", step_index=1, state="DONE", step_type="tool"),
    agy_line("step_update", step_index=2, state="ACTIVE", step_type="tool"),
    agy_line("step_update", step_index=2, state="ERROR", step_type="tool"),
    agy_line("step_update", step_index=3, state="ACTIVE", step_type="agent_response"),
    "not json",
    agy_line("result", status="SUCCESS", duration_seconds=597.1,
             usage={"input_tokens": 149192, "output_tokens": 15043, "total_tokens": 164235}),
])


def test_codex_counts_commands_failures_and_the_last_token_total():
    e = parse_codex(CODEX_LOG)
    assert e == {"tokens": 60071, "calls": 3, "failed_calls": 1}


def test_codex_without_a_token_line_reports_none_not_zero():
    assert parse_codex("codex\nexec\nls\n succeeded in 0ms:\n")["tokens"] is None


def test_agy_counts_each_tool_step_once_and_its_errors():
    e = parse_agy(AGY_LOG)
    assert e == {"tokens": 164235, "calls": 2, "failed_calls": 1}


def test_agy_without_a_result_reports_none_tokens():
    assert parse_agy(agy_line("step_update", step_index=1, state="DONE", step_type="tool"))["tokens"] is None


def test_run_effort_picks_the_parser_and_measures_wall_minutes(tmp_path):
    for name, log in (("codex-run", CODEX_LOG), ("agy-run", AGY_LOG)):
        d = tmp_path / name
        d.mkdir()
        (d / "prompt.md").write_text("p")
        (d / "log").write_text(log)
        (d / "exit").write_text("0\n")
        os.utime(d / "prompt.md", (1000, 1000))
        os.utime(d / "exit", (1000 + 330, 1000 + 330))
    c = run_effort(tmp_path / "codex-run")
    g = run_effort(tmp_path / "agy-run")
    assert c["agent"] == "codex" and c["calls"] == 3 and c["minutes"] == 5.5 and c["exit"] == "0"
    assert g["agent"] == "agy" and g["tokens"] == 164235 and g["minutes"] == 5.5


def oc_line(type_, **body):
    return json.dumps({"type": type_, "timestamp": 1, "sessionID": "ses_x", **body})


def oc_step(total):
    return oc_line("step_finish", part={"type": "step-finish", "reason": "stop",
                                        "tokens": {"total": total, "input": 1, "output": 1}})


OPENCODE_LOG = "\n".join([
    oc_line("step_start", part={"type": "step-start"}),
    oc_line("tool_use", part={"tool": "bash", "state": {"status": "completed"}}),
    oc_line("tool_use", part={"tool": "bash", "state": {"status": "error"}}),
    oc_step(8000),
    oc_line("tool_use", part={"tool": "write", "state": {"status": "completed"}}),
    oc_line("text", part={"text": "done"}),
    oc_step(8380),
])


def test_opencode_sums_the_steps_and_counts_failed_tools():
    # each step_finish reports the tokens of one model request; the run's total is their sum
    e = parse_opencode(OPENCODE_LOG)
    assert e == {"tokens": 16380, "calls": 3, "failed_calls": 1}


def test_opencode_that_stopped_on_an_api_error_reports_none_tokens():
    err = oc_line("error", error={"name": "APIError", "data": {"statusCode": 429}})
    assert parse_opencode(err) == {"tokens": None, "calls": 0, "failed_calls": 0}


def test_run_effort_recognises_an_opencode_log(tmp_path):
    d = tmp_path / "oc-run"
    d.mkdir()
    (d / "prompt.md").write_text("p")
    (d / "log").write_text(OPENCODE_LOG)
    (d / "exit").write_text("0\n")
    r = run_effort(d)
    assert r["agent"] == "opencode" and r["tokens"] == 16380 and r["calls"] == 3
