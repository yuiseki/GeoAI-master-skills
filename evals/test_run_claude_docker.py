"""Tests for run_claude_docker.sh, through --dry-run (no Docker needed): the limits, mounts and what reaches Claude
Code are the eval condition."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "run_claude_docker.sh"
TOKEN = "sk-ant-oat01-secret"


def run(*args, home, env=None):
    e = {k: v for k, v in os.environ.items() if k not in ("EVAL_CLAUDE_HOME", "CLAUDE_CODE_OAUTH_TOKEN")}
    e.update({"HOME": str(home), **(env or {})})
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, env=e)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    (h / ".claude-evals").mkdir(parents=True)
    (h / ".claude-evals" / "oauth_token").write_text(TOKEN + "\n")
    return h


@pytest.fixture
def workdir(tmp_path):
    w = tmp_path / "w"
    (w / "projects").mkdir(parents=True)
    return w


def test_hard_limits_are_the_codex_ones(home, workdir):
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode == 0, r.stderr
    for flag in ["--cpuset-cpus=0-7", "--cpus=8", "--memory=16g", "--memory-swap=16g",
                 "--pids-limit=512", "--cap-drop=ALL", "--security-opt=no-new-privileges"]:
        assert flag in r.stdout


def test_only_the_workdir_is_mounted_and_the_token_is_passed_by_name_not_value(home, workdir):
    out = run("--dry-run", str(workdir), home=home).stdout
    assert out.count(" -v ") == 1 and f"{workdir}:/work" in out
    assert "-e CLAUDE_CODE_OAUTH_TOKEN " in out and TOKEN not in out
    assert "docker.sock" not in out and ".claude:" not in out


def test_claude_runs_non_interactively_with_json_events_and_a_free_shell(home, workdir, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("go")
    out = run("--prompt", str(p), "--dry-run", str(workdir), "--model", "claude-sonnet-5-5", home=home).stdout
    for flag in ["claude -p", "--output-format stream-json", "--verbose", "--dangerously-skip-permissions",
                 "--strict-mcp-config", "--no-session-persistence", "--model claude-sonnet-5-5"]:
        assert flag in out
    assert "-i " in out


def test_context_is_mounted_read_only_as_the_claude_md_above_the_workdir(home, workdir, tmp_path):
    c = tmp_path / "global.md"
    c.write_text("rules")
    out = run("--context", str(c), "--dry-run", str(workdir), home=home).stdout
    assert out.count(" -v ") == 2 and f"{c}:/CLAUDE.md:ro" in out


def test_no_token_is_refused(home, workdir):
    (home / ".claude-evals" / "oauth_token").unlink()
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode != 0 and "setup-token" in r.stderr


def test_a_workdir_with_evals_is_refused(home, workdir):
    (workdir / "evals").mkdir()
    assert run("--dry-run", str(workdir), home=home).returncode != 0
