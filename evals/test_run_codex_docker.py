"""Tests for run_codex_docker.sh, through --dry-run (no Docker needed): the limits and mounts are the eval condition."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "run_codex_docker.sh"


def run(*args, home, env=None):
    e = {k: v for k, v in os.environ.items() if k != "EVAL_CODEX_HOME"}
    e.update({"HOME": str(home), **(env or {})})
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, env=e)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    (h / ".codex-evals").mkdir(parents=True)
    (h / ".codex-evals" / "auth.json").write_text("{}")
    return h


@pytest.fixture
def workdir(tmp_path):
    w = tmp_path / "w"
    (w / "projects").mkdir(parents=True)
    return w


def test_hard_limits_are_set(home, workdir):
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode == 0, r.stderr
    for flag in ["--cpuset-cpus=0-7", "--cpus=8", "--memory=16g", "--memory-swap=16g",
                 "--pids-limit=512", "--cap-drop=ALL", "--security-opt=no-new-privileges"]:
        assert flag in r.stdout


def test_only_the_workdir_and_codex_state_are_mounted(home, workdir):
    out = run("--dry-run", str(workdir), home=home).stdout
    assert out.count(" -v ") == 2
    assert f"{workdir}:/work" in out and f"{home}/.codex-evals:/home/geo/.codex" in out
    assert "docker.sock" not in out


def test_extra_arguments_reach_codex(home, workdir):
    out = run("--dry-run", str(workdir), "-m", "gpt-6-luna", "-c", "model_reasoning_effort=medium",
              home=home).stdout
    assert "-m gpt-6-luna -c model_reasoning_effort=medium" in out


def test_prompt_runs_exec_reading_stdin(home, workdir, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("go")
    out = run("--prompt", str(p), "--dry-run", str(workdir), home=home).stdout
    assert "codex exec" in out and out.strip().endswith("-")


def test_refuses_a_workdir_holding_evals_or_git(home, workdir):
    (workdir / "evals").mkdir()
    assert run("--dry-run", str(workdir), home=home).returncode == 2


def test_refuses_without_a_login(tmp_path, workdir):
    r = run("--dry-run", str(workdir), home=tmp_path)
    assert r.returncode == 2 and "--login" in r.stderr


def test_refuses_the_everyday_codex_dir(home, workdir):
    (home / ".codex").mkdir()
    r = run("--dry-run", str(workdir), home=home, env={"EVAL_CODEX_HOME": str(home / ".codex")})
    assert r.returncode == 2
