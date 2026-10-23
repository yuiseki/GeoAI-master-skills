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


def test_prompt_workdir_overrides_the_path_in_the_prompt(repo, tmp_path):
    (repo / "t.md").write_text("## 課題 1: a\n問い\n")
    (repo / "tpl.md").write_text("at {{WORKDIR}} {{SHA}}\n{{TASK}}")
    here = Path(__file__).parent
    out = subprocess.run(
        ["python", str(here / "prepare_workdir.py"), "HEAD", str(tmp_path / "w"), "--repo", str(repo),
         "--task", str(repo / "t.md"), "--number", "1", "--template", str(repo / "tpl.md"),
         "--prompt-workdir", "/work"], check=True, capture_output=True, text=True).stdout
    assert out.startswith("at /work ")


def test_render_prompt_keeps_the_skills_part_only_with_skills():
    t = "a\n{{#SKILLS}}read the skills\n{{/SKILLS}}{{#BASELINE}}no skills here\n{{/BASELINE}}b"
    assert render_prompt(t, Path("/w"), "T", "s") == "a\nread the skills\nb"
    assert render_prompt(t, Path("/w"), "T", "s", baseline=True) == "a\nno skills here\nb"


def test_extract_table_returns_the_csv_block_of_the_task():
    from prepare_workdir import extract_table
    task = "## 課題 1: a\n\n表:\n\n```csv\nid,v\n1,2\n3,4\n```\n"
    assert extract_table(task) == "id,v\n1,2\n3,4\n"
    with pytest.raises(SystemExit):
        extract_table("## 課題 2: b\n\n表は無い\n")


def test_table_file_is_written_the_same_for_baseline_and_skills(repo, tmp_path):
    # the table must reach both conditions as the same file, and the prompt must say where it is
    (repo / "t.md").write_text("## 課題 1: a\n\n```csv\nid,v\n1,2\n```\n")
    (repo / "tpl.md").write_text("at {{WORKDIR}}\n{{TASK}}")
    here = Path(__file__).parent
    outs = {}
    for name, flag in (("s", []), ("b", ["--baseline"])):
        outs[name] = subprocess.run(
            ["python", str(here / "prepare_workdir.py"), "HEAD", str(tmp_path / name), "--repo", str(repo),
             "--task", str(repo / "t.md"), "--number", "1", "--template", str(repo / "tpl.md"),
             "--prompt-workdir", "/work", "--table-file", "task1.csv", *flag],
            check=True, capture_output=True, text=True).stdout
        assert (tmp_path / name / "data" / "task1.csv").read_text() == "id,v\n1,2\n"
        assert "/work/data/task1.csv" in outs[name]
    assert outs["s"] == outs["b"]


def test_time_limit_is_stated_the_same_for_baseline_and_skills(repo, tmp_path):
    # the runner kills the run at the limit; the agent must be told, in both conditions alike
    (repo / "t.md").write_text("## 課題 1: a\n\nq\n")
    (repo / "tpl.md").write_text("at {{WORKDIR}}\n{{TASK}}")
    here = Path(__file__).parent
    outs = {}
    for name, flag in (("s", []), ("b", ["--baseline"])):
        outs[name] = subprocess.run(
            ["python", str(here / "prepare_workdir.py"), "HEAD", str(tmp_path / name), "--repo", str(repo),
             "--task", str(repo / "t.md"), "--number", "1", "--template", str(repo / "tpl.md"),
             "--prompt-workdir", "/work", "--time-limit", "60", *flag],
            check=True, capture_output=True, text=True).stdout
        assert "60 分" in outs[name] and "/work/projects/" in outs[name]
    assert outs["s"] == outs["b"]
    without = subprocess.run(
        ["python", str(here / "prepare_workdir.py"), "HEAD", str(tmp_path / "n"), "--repo", str(repo),
         "--task", str(repo / "t.md"), "--number", "1", "--template", str(repo / "tpl.md"), "--baseline"],
        check=True, capture_output=True, text=True).stdout
    assert "分で打ち切" not in without


def test_hide_removes_a_dataset_the_task_keeps_as_its_answer(repo, tmp_path):
    # task 28 grades against mlit-underpass: its card (with the counts) and every line naming it must be gone
    refs = repo / ".agents" / "skills" / "x" / "references"
    refs.mkdir()
    (refs / "secret-set.md").write_text("Tokyo has 153 points\n")
    (refs / "index.md").write_text("| [other](other.md) | a |\n| [secret-set](secret-set.md) | answer |\n")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "card")
    dest = tmp_path / "w"
    prepare(repo, "HEAD", dest, baseline=False, hide=["secret-set"])
    assert not (dest / ".agents/skills/x/references/secret-set.md").exists()
    assert (dest / ".agents/skills/x/references/index.md").read_text() == "| [other](other.md) | a |\n"
    assert not any("secret-set" in p.read_text() for p in dest.rglob("*") if p.is_file())


@pytest.mark.parametrize("ref", ["evals/results/x-2026-10-17.md", "evals/tasks/small-rubric-3.md"])
def test_refuses_a_copy_whose_files_point_into_the_results_or_the_tasks(repo, tmp_path, ref):
    # an index of results kept outside evals/ (docs/eval-status.md was one) hands the answers to the agent
    (repo / "docs" / "status.md").write_text(f"see `{ref}`: the court is in the palace\n")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "leak")
    with pytest.raises(SystemExit, match="docs/status.md"):
        prepare(repo, "HEAD", tmp_path / "w", baseline=False)


def test_the_repository_itself_makes_a_clean_copy(tmp_path):
    # the tracked files as they stand, committed or not (stash create makes a commit without touching the tree)
    repo = Path(__file__).resolve().parent.parent
    rev = subprocess.run(["git", "-C", str(repo), "stash", "create"], check=True, capture_output=True,
                         text=True).stdout.strip() or "HEAD"
    prepare(repo, rev, tmp_path / "w", baseline=False)


def test_the_repository_keeps_analyses_out_of_git_but_the_sample_in():
    # agents work in projects/<name>/ and artifacts/<name>/; only the sample layout is tracked
    repo = Path(__file__).resolve().parent.parent

    def ignored(path):
        return subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", path]).returncode == 0

    assert ignored("projects/some-analysis/report.md") and ignored("artifacts/some-analysis/big.parquet")
    assert not ignored("projects/sample-project/README.md") and not ignored("artifacts/sample-project/README.md")
    assert (repo / "projects" / "sample-project" / "README.md").exists()
    assert (repo / "artifacts" / "sample-project" / "README.md").exists()
