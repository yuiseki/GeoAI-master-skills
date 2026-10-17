"""Tests for run_opencode_docker.sh, through --dry-run (no Docker, no network): limits, mounts, model and config."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "run_opencode_docker.sh"


def run(*args, home, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("EVAL_", "OPENCODE_"))}
    e.update({"HOME": str(home), **(env or {})})
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, env=e)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    (h / ".config/opencode").mkdir(parents=True)
    (h / ".local/share/opencode").mkdir(parents=True)
    return h


@pytest.fixture
def workdir(tmp_path):
    w = tmp_path / "w"
    (w / "projects").mkdir(parents=True)
    return w


def test_hard_limits_are_the_same_as_the_other_runners(home, workdir):
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode == 0, r.stderr
    for flag in ["--cpuset-cpus=0-7", "--cpus=8", "--memory=16g", "--memory-swap=16g",
                 "--pids-limit=512", "--cap-drop=ALL", "--security-opt=no-new-privileges"]:
        assert flag in r.stdout


def test_only_the_workdir_is_mounted(home, workdir):
    # no everyday config, auth or state: nothing from $HOME, no docker.sock
    out = run("--dry-run", str(workdir), home=home).stdout
    assert out.count(" -v ") == 1 and f"{workdir}:/work" in out
    assert str(home) not in out and "docker.sock" not in out


def test_everyday_opencode_variables_are_not_passed(home, workdir):
    out = run("--dry-run", str(workdir), home=home,
              env={"OPENCODE_CONFIG": "/x/opencode.json", "OPENCODE_API_KEY": "sekrit"}).stdout
    assert "/x/opencode.json" not in out and "sekrit" not in out and "OPENCODE_API_KEY" not in out


def test_prompt_runs_opencode_run_with_json_events_and_auto(home, workdir, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("go")
    out = run("--prompt", str(p), "--dry-run", str(workdir), home=home).stdout
    assert "opencode run" in out and "--format json" in out and "--auto" in out and "--pure" in out
    assert "--dir /work" in out and " -i " in out and " -it " not in out


def test_default_model_and_the_override(home, workdir, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("go")
    out = run("--prompt", str(p), "--dry-run", str(workdir), home=home).stdout
    assert "--model opencode/deepseek-v4.1-flash-free" in out
    out = run("--prompt", str(p), "--dry-run", str(workdir), home=home,
              env={"EVAL_MODEL": "opencode/glm-5.3-flash-free"}).stdout
    assert "--model opencode/glm-5.3-flash-free" in out and "deepseek" not in out


def test_extra_arguments_come_last(home, workdir, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("go")
    out = run("--prompt", str(p), "--dry-run", str(workdir), "--variant", "high", home=home).stdout
    assert out.rstrip().endswith("--variant high")


def test_sharing_and_updates_are_off_in_the_inline_config(home, workdir):
    out = run("--dry-run", str(workdir), home=home).stdout.replace("\\", "")
    assert "OPENCODE_CONFIG_CONTENT=" in out
    assert '"share":"disabled"' in out and '"autoupdate":false' in out


def test_without_prompt_starts_the_interactive_tui(home, workdir):
    out = run("--dry-run", str(workdir), home=home).stdout
    assert " -it " in out and "opencode run" not in out and "--model opencode/deepseek-v4.1-flash-free" in out


def test_refuses_a_workdir_holding_evals_or_git(home, workdir):
    (workdir / "evals").mkdir()
    assert run("--dry-run", str(workdir), home=home).returncode == 2
    (workdir / "evals").rmdir()
    (workdir / ".git").mkdir()
    assert run("--dry-run", str(workdir), home=home).returncode == 2


def test_refuses_a_missing_prompt_file(home, workdir, tmp_path):
    r = run("--prompt", str(tmp_path / "none.md"), "--dry-run", str(workdir), home=home)
    assert r.returncode == 2
