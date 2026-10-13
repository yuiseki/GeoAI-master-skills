"""Tests for prepare_workdir.py: the agent's working copy must never contain evals/."""

import subprocess
from pathlib import Path

import pytest

from prepare_workdir import prepare, render_prompt


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "evals" / "tasks").mkdir(parents=True)
    (r / ".agents" / "skills" / "x").mkdir(parents=True)
    (r / "docs").mkdir()
    (r / "projects").mkdir()
    (r / "evals" / "tasks" / "rubric.md").write_text("answer\n")
    (r / ".agents" / "skills" / "x" / "SKILL.md").write_text("skill\n")
    (r / "docs" / "glossary.md").write_text("g\n")
    (r / "AGENTS.md").write_text("flow\n")
    (r / "projects" / ".gitkeep").write_text("")
    git(r, "init", "-q")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    return r


def test_with_skills_copy_has_skills_but_no_evals(repo, tmp_path):
    dest = tmp_path / "w"
    prepare(repo, "HEAD", dest, baseline=False)
    assert (dest / "AGENTS.md").exists()
    assert (dest / ".agents/skills/x/SKILL.md").exists()
    assert not (dest / "evals").exists()


def test_evals_removed_even_without_export_ignore(repo, tmp_path):
    # the repo fixture has no .gitattributes; the script must not rely on it
    dest = tmp_path / "w"
    prepare(repo, "HEAD", dest, baseline=False)
    assert not any("rubric" in p.name for p in dest.rglob("*"))


def test_baseline_has_only_projects(repo, tmp_path):
    dest = tmp_path / "w"
    prepare(repo, "HEAD", dest, baseline=True)
    names = sorted(p.name for p in dest.iterdir())
    assert names == ["projects"]


def test_refuses_existing_destination(repo, tmp_path):
    dest = tmp_path / "w"
    dest.mkdir()
    (dest / "keep").write_text("x")
    with pytest.raises(SystemExit):
        prepare(repo, "HEAD", dest, baseline=False)
    assert (dest / "keep").exists()


def test_render_prompt_fills_workdir_and_task():
    t = "dir={{WORKDIR}} sha={{SHA}}\n{{TASK}}"
    out = render_prompt(t, Path("/w/x"), "TASKTEXT", "abc123")
    assert out == "dir=/w/x sha=abc123\nTASKTEXT"


def test_extract_task_returns_only_that_section():
    from prepare_workdir import extract_task
    text = "# head\n\n## 課題 1: a\n\nbody1\n\n## 課題 2: b\n\nbody2\n\n## 課題 10: c\n\nbody10\n"
    assert extract_task(text, 2) == "## 課題 2: b\n\nbody2\n"
    assert extract_task(text, 10) == "## 課題 10: c\n\nbody10\n"
    with pytest.raises(SystemExit):
        extract_task(text, 3)
