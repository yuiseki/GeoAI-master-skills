"""Tests for run_claude_local.sh, through --dry-run (no claude needed): what reaches the agent is the eval condition."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "run_claude_local.sh"


def run(*args, home):
    e = dict(os.environ, HOME=str(home))
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, env=e)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    (h / ".claude").mkdir(parents=True)
    return h


@pytest.fixture
def workdir(tmp_path):
    w = tmp_path / "base" / "w"
    (w / "projects").mkdir(parents=True)
    return w


def test_no_user_settings_no_mcp_no_session_and_json_events(home, workdir):
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode == 0, r.stderr
    for flag in ["claude -p", "--setting-sources project", "--strict-mcp-config", "--no-session-persistence",
                 "--output-format stream-json", "--verbose"]:
        assert flag in r.stdout
    assert f"cd {workdir}" in r.stdout


def test_only_reading_tools_are_allowed(home, workdir):
    out = run("--dry-run", str(workdir), home=home).stdout
    assert "--allowedTools Read,Grep,Glob,Bash(cat:*)" in out
    assert "Edit" not in out and "Write" not in out and "WebFetch" not in out


def test_extra_arguments_reach_claude_and_the_prompt_is_stdin(home, workdir, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("go")
    out = run("--prompt", str(p), "--dry-run", str(workdir), "--model", "claude-sonnet-5-5", home=home).stdout
    assert "--model claude-sonnet-5-5" in out and f"< {p}" in out


def test_a_claude_md_above_the_workdir_is_refused(home, workdir):
    """Claude Code reads every CLAUDE.md above its folder: one there would be a condition nobody set."""
    (workdir.parent / "CLAUDE.md").write_text("rules")
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode != 0 and "CLAUDE.md" in r.stderr


def test_a_user_claude_md_is_refused(home, workdir):
    (home / ".claude" / "CLAUDE.md").write_text("rules")
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode != 0 and "CLAUDE.md" in r.stderr


def test_context_puts_the_given_file_as_claude_md_just_above_the_workdir(home, workdir, tmp_path):
    c = tmp_path / "global.md"
    c.write_text("日本語の丁寧語で応答せよ。")
    r = run("--context", str(c), "--dry-run", str(workdir), home=home)
    assert r.returncode == 0, r.stderr
    assert (workdir.parent / "CLAUDE.md").read_text() == "日本語の丁寧語で応答せよ。"
