"""Tests for effort.py: how much work a run took, read from the agent's own log."""

import json
import os

from effort import parse_agy, parse_codex, run_effort

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
