"""uvx --python 3.12 --with pytest pytest -q test_run_tests.py"""

# Tests for run_tests.py: each test file is run the way its first line says, and the files that say nothing are
# run together under the pinned toolchain.

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from run_tests import ROOT, declared, plan  # noqa: E402


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_uvx_line_runs_in_the_file_s_folder(tmp_path):
    f = write(tmp_path / "s" / "scripts" / "test_a.py",
              '"""uvx --from \'duckdb>=1.5.5\' --with pytest pytest test_a.py"""\n')
    assert declared(f, tmp_path) == (["uvx", "--from", "duckdb>=1.5.5", "--with", "pytest", "pytest", "test_a.py"],
                                     f.parent)


def test_the_first_line_of_a_longer_docstring_is_the_command(tmp_path):
    f = write(tmp_path / "test_b.py", '"""uvx --python 3.12 --with pytest pytest -q test_b.py\n\nMore words.\n"""\n')
    assert declared(f, tmp_path)[0][-2:] == ["-q", "test_b.py"]


def test_run_with_python3_runs_from_the_repository_root(tmp_path):
    f = write(tmp_path / ".agents" / "skills" / "test_c.py",
              '"""Run with: python3 .agents/skills/test_c.py"""\n')
    assert declared(f, tmp_path) == (["python3", ".agents/skills/test_c.py"], tmp_path)


def test_a_comment_line_and_a_path_from_the_skill_folder(tmp_path):
    """Some skills write `# uvx ... pytest scripts/test_x.py`: run it from the folder the path is relative to."""
    f = write(tmp_path / "skill" / "scripts" / "test_g.py", "# uvx --with pytest pytest scripts/test_g.py  # noqa: E501\nimport json\n")
    assert declared(f, tmp_path) == (["uvx", "--with", "pytest", "pytest", "scripts/test_g.py"], tmp_path / "skill")


def test_a_path_from_the_repository_root(tmp_path):
    f = write(tmp_path / ".agents" / "skills" / "q" / "scripts" / "test_h.py",
              "# uvx --with pytest python -m pytest -q .agents/skills/q/scripts/test_h.py\n")
    assert declared(f, tmp_path)[1] == tmp_path


def test_a_file_that_declares_nothing_has_no_command(tmp_path):
    assert declared(write(tmp_path / "test_d.py", '"""Tests for d.py."""\n'), tmp_path) is None
    assert declared(write(tmp_path / "test_e.py", "import json\n"), tmp_path) is None


def test_only_known_runners_are_taken(tmp_path):
    f = write(tmp_path / "test_f.py", '"""rm -rf / && pytest test_f.py"""\n')
    assert declared(f, tmp_path) is None


def test_the_plan_runs_the_rest_together_under_the_lock(tmp_path):
    write(tmp_path / "evals" / "test_x.py", '"""Tests for x."""\n')
    write(tmp_path / "evals" / "test_y.py", '"""Tests for y."""\n')
    write(tmp_path / "evals" / "s" / "test_z.py", '"""uvx --with pytest pytest test_z.py"""\n')
    write(tmp_path / "evals" / "helper.py", "")
    jobs = plan(["evals"], tmp_path)
    assert len(jobs) == 2
    own, rest = sorted(jobs, key=lambda j: len(j["files"]))
    assert own["argv"] == ["uvx", "--with", "pytest", "pytest", "test_z.py"]
    assert rest["cwd"] == tmp_path and rest["files"] == ["evals/test_x.py", "evals/test_y.py"]
    assert "--with-requirements" in rest["argv"] and "evals/requirements-evals.lock" in rest["argv"]
    assert rest["argv"][-2:] == ["evals/test_x.py", "evals/test_y.py"]


def test_the_repository_s_default_roots_are_all_planned():
    jobs = plan(None, ROOT)
    files = [f for j in jobs for f in j["files"]]
    assert any(f.startswith(".agents/skills/") for f in files)
    assert "evals/test_trigger.py" in files and "tools/test_run_tests.py" in files
    assert not any(f.startswith("projects/") for f in files)
    assert len(files) == len(set(files))


def test_the_local_python_s_geo_variables_do_not_reach_the_tests():
    """Anaconda's PROJ_DATA pointed rasterio's wheel at an older proj.db (EPSG unknown, 2026-11-11)."""
    from run_tests import clean_env
    env = clean_env({"PATH": "/bin", "HOME": "/h", "PROJ_DATA": "/a", "PROJ_LIB": "/a", "GDAL_DATA": "/a",
                     "GDAL_DRIVER_PATH": "/a", "PYTHONPATH": "/a", "CONDA_PREFIX": "/a", "UV_CACHE_DIR": "/c"})
    assert env == {"PATH": "/bin", "HOME": "/h", "UV_CACHE_DIR": "/c", "UV_PYTHON": "3.12"}


def test_each_job_gets_a_fixed_number_of_threads():
    """Four jobs of scikit-learn with 78 threads each crawled under a 400 % CPU limit (2026-11-11)."""
    from run_tests import clean_env
    env = clean_env({"PATH": "/bin", "OMP_NUM_THREADS": "32"}, threads=2)
    assert {env[k] for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                             "NUMEXPR_NUM_THREADS")} == {"2"}


def test_uvx_picks_the_same_python_everywhere_unless_told():
    """Without it uvx took 3.13 here and 3.11 on GitHub, where pyproj then had to build from source."""
    from run_tests import clean_env
    assert clean_env({"PATH": "/bin"})["UV_PYTHON"] == "3.12"
    assert clean_env({"PATH": "/bin", "UV_PYTHON": "3.13"})["UV_PYTHON"] == "3.13"
