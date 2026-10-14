"""Tests for run_gemini_docker.sh, through --dry-run (no Docker, no network): limits, mounts and the key handling."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "run_gemini_docker.sh"
KEYS = ("GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY", "EVAL_ENV_FILE", "EVAL_GEMINI_HOME")


def run(*args, home, env=None):
    e = {k: v for k, v in os.environ.items() if k not in KEYS}
    e.update({"HOME": str(home), "EVAL_ENV_FILE": str(home / "none.env"), **(env or {})})
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, env=e)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def workdir(tmp_path):
    w = tmp_path / "w"
    (w / "projects").mkdir(parents=True)
    return w


KEY = {"GEMINI_API_KEY": "sekrit-value-123"}


def test_hard_limits_are_set(home, workdir):
    r = run("--dry-run", str(workdir), home=home, env=KEY)
    assert r.returncode == 0, r.stderr
    for flag in ["--cpuset-cpus=0-7", "--cpus=8", "--memory=16g", "--memory-swap=16g",
                 "--pids-limit=512", "--cap-drop=ALL", "--security-opt=no-new-privileges"]:
        assert flag in r.stdout


def test_only_the_workdir_and_agy_state_are_mounted(home, workdir):
    out = run("--dry-run", str(workdir), home=home, env=KEY).stdout
    assert out.count(" -v ") == 2
    assert f"{workdir}:/work" in out and f"{home}/.gemini-evals:/home/geo/.gemini" in out
    assert "docker.sock" not in out


def test_the_key_is_passed_by_name_and_never_printed(home, workdir):
    out = run("--dry-run", str(workdir), home=home, env=KEY).stdout
    assert "-e GEMINI_API_KEY " in out and "sekrit-value-123" not in out


def test_settings_select_the_gemini_api_provider(home, workdir):
    run("--dry-run", str(workdir), home=home, env=KEY)
    s = (home / ".gemini-evals/antigravity-cli/settings.json").read_text()
    assert '"modelProvider": "gemini"' in s and "sekrit" not in s


def test_env_file_supplies_the_key_and_other_secrets_stay_out(home, workdir):
    f = home / "x.env"
    f.write_text("OTHER_TOKEN=leak-me\nexport GOOGLE_GENERATIVE_AI_API_KEY='from-file'\n")
    r = run("--dry-run", str(workdir), home=home, env={"EVAL_ENV_FILE": str(f)})
    assert r.returncode == 0 and "leak-me" not in r.stdout and "from-file" not in r.stdout
    assert "-e GEMINI_API_KEY " in r.stdout


def test_refuses_without_a_key(home, workdir):
    r = run("--dry-run", str(workdir), home=home)
    assert r.returncode == 2 and ".env.example" in r.stderr


def test_default_model_is_a_weak_flash_with_low_effort_and_can_be_overridden(home, workdir):
    out = run("--dry-run", str(workdir), home=home, env=KEY).stdout
    assert "--model gemini-3.6-flash --effort low" in out and "--dangerously-skip-permissions" in out
    out = run("--dry-run", str(workdir), "--effort", "medium", home=home, env=KEY).stdout
    assert out.rstrip().endswith("--effort medium")


def test_prompt_runs_print_mode_with_a_structured_log(home, workdir, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("go")
    out = run("--prompt", str(p), "--dry-run", str(workdir), home=home, env=KEY).stdout.replace("\\", "")
    assert "--print=" in out and "--output-format stream-json" in out and "--print -" not in out


def test_refuses_a_workdir_holding_evals_or_git(home, workdir):
    (workdir / "evals").mkdir()
    assert run("--dry-run", str(workdir), home=home, env=KEY).returncode == 2


def test_refuses_the_everyday_gemini_dir(home, workdir):
    (home / ".gemini").mkdir()
    r = run("--dry-run", str(workdir), home=home, env={**KEY, "EVAL_GEMINI_HOME": str(home / ".gemini")})
    assert r.returncode == 2


# OAuth sign-in: the key is not needed and not passed; the state directory holds the token.
def with_token(home):
    d = home / ".gemini-evals/antigravity-cli"
    d.mkdir(parents=True)
    (d / "antigravity-oauth-token").write_text("t")


def test_oauth_needs_no_key_and_passes_none(home, workdir):
    r = run("--auth", "oauth", "--dry-run", str(workdir), home=home, env=KEY)
    assert r.returncode == 0, r.stderr
    assert "-e GEMINI_API_KEY" not in r.stdout
    assert '"modelProvider"' not in (home / ".gemini-evals/antigravity-cli/settings.json").read_text()


def test_auth_is_oauth_by_default_when_a_token_exists(home, workdir):
    with_token(home)
    r = run("--dry-run", str(workdir), home=home, env=KEY)
    assert r.returncode == 0 and "-e GEMINI_API_KEY" not in r.stdout and "auth: oauth" in r.stderr


def test_auth_falls_back_to_the_key_without_a_token(home, workdir):
    r = run("--dry-run", str(workdir), home=home, env=KEY)
    assert "-e GEMINI_API_KEY " in r.stdout and "auth: api-key" in r.stderr


def test_login_starts_an_interactive_agy_with_only_the_state_mounted(home):
    r = run("--login", "--dry-run", home=home)
    assert r.returncode == 0, r.stderr
    assert " -it " in r.stdout and r.stdout.count(" -v ") == 1 and "/work" not in r.stdout
    assert "--cpuset-cpus=0-7" in r.stdout and "-e GEMINI_API_KEY" not in r.stdout


def test_oauth_default_model_has_the_effort_in_its_name_and_no_effort_flag(home, workdir):
    out = run("--auth", "oauth", "--dry-run", str(workdir), home=home).stdout
    assert "--model gemini-3.8-flash-low" in out and "--effort" not in out
    out = run("--auth", "oauth", "--dry-run", str(workdir), home=home,
              env={"EVAL_MODEL": "gemini-3.8-flash-medium"}).stdout
    assert "--model gemini-3.8-flash-medium" in out
