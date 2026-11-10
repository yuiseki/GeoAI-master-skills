"""Tests for run_qoder_docker.sh, through --dry-run (no Docker needed): the limits, mounts and what reaches qodercli are the eval condition."""

import os
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "run_qoder_docker.sh"
TOKEN = "pt-qoder-secret"


def run(*args, home, env=None):
    e = {k: v for k, v in os.environ.items() if k not in ("EVAL_QODER_HOME", "QODER_PERSONAL_ACCESS_TOKEN")}
    e.update({"HOME": str(home), **(env or {})})
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, env=e)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    (h / ".qoder-evals").mkdir(parents=True)
    (h / ".qoder-evals" / "pat").write_text(TOKEN + "\n")
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
    assert "-e QODER_PERSONAL_ACCESS_TOKEN " in out and TOKEN not in out
    assert "docker.sock" not in out and ".qoder:" not in out


def test_qodercli_runs_non_interactively_with_json_events_and_a_free_shell(home, workdir, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("go")
    out = run("--prompt", str(p), "--dry-run", str(workdir), "--model", "auto", home=home).stdout
    for flag in ["qodercli -p", "--output-format stream-json", "--dangerously-skip-permissions",
                 "--strict-mcp-config", "--no-session-persistence", "--model auto"]:
        assert flag in out
    assert "-i " in out


def test_there_is_no_context_option(home, workdir, tmp_path):
    c = tmp_path / "global.md"
    c.write_text("rules")
    assert run("--context", str(c), "--dry-run", str(workdir), home=home).returncode != 0


def test_no_token_is_refused(home, workdir):
    (home / ".qoder-evals" / "pat").unlink()
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode != 0 and "qoder.com" in r.stderr


def test_a_workdir_with_evals_is_refused(home, workdir):
    (workdir / "evals").mkdir()
    assert run("--dry-run", str(workdir), home=home).returncode != 0


def test_the_everyday_qoder_home_is_refused(home, workdir):
    (home / ".qoder").mkdir()
    (home / ".qoder" / "pat").write_text(TOKEN)
    r = run("--dry-run", str(workdir), home=home, env={"EVAL_QODER_HOME": str(home / ".qoder")})
    assert r.returncode != 0


ROOT = Path(__file__).parent.parent


def test_the_image_is_built_from_pinned_inputs_only():
    """Rebuilding Dockerfile.evals.qoder later must give the same toolchain: the base images by digest, the CLI
    by version, every Python package by exact version from the lock (no >= or bare names)."""
    d = (ROOT / "Dockerfile.evals.qoder").read_text()
    froms = [l for l in d.splitlines() if l.startswith(("FROM", "COPY --from"))]
    assert froms and all("@sha256:" in l for l in froms), froms
    assert "ARG QODER_VERSION=1.1.86" in d
    assert "requirements-evals.lock" in d and ">=" not in d.split("requirements-evals.lock")[0].split("uv venv")[-1]
    lock = [l for l in (ROOT / "evals" / "requirements-evals.lock").read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    assert lock and all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", l) for l in lock), lock
    assert "duckdb==1.5.6" in lock and "rasterio==1.4.1" in lock
