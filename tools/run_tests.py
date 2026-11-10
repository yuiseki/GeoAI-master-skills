"""Run every test of the repository the way it says it runs.

    python3 tools/run_tests.py [ROOT ...] [--jobs N] [--list]

A test file names its own command on its first line, the docstring (the rule of .agents/skills/check_skills.py:
`uvx --with duckdb --with pytest pytest test_x.py`, also as a # comment, run from the folder its path to the file
is relative to; or `Run with: python3 <path>`, run
from the repository root). Running them all with one bare `pytest` instead gives every test whatever packages the
local Python has (a DuckDB 1.3 made 43 tests of evals/curriculum fail on 2026-11-10). Test files that name no
command (evals/test_*.py) run together, with pytest, under the pinned toolchain of the eval images
(evals/requirements-evals.lock).

ROOT: folders to search (default .agents/skills, evals, docs, tools). projects/ is left out: its tests mostly
name no command and some read data that is not in the repository.

Exit status 1 when any test fails. Wrap the whole run in a memory and CPU limit on a shared machine.
"""

import argparse
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOTS = [".agents/skills", "evals", "docs", "tools"]
LOCK = "evals/requirements-evals.lock"
RUNNERS = {"uvx", "uv", "python3"}
# Thread pools of the numeric libraries. Unset, each job starts one thread per core, and several jobs under a CPU
# limit spend their time waiting on each other.
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
SKIP = {"__pycache__", ".pytest_cache", "node_modules", ".venv"}


def declared(path, root=ROOT):
    """The command a test file names on its first line, and the folder to run it from; None when it names none."""
    try:
        first = Path(path).read_text(encoding="utf-8").splitlines()[0]
    except (IndexError, UnicodeDecodeError):
        return None
    line = first.strip()
    for q in ('"""', "'''"):
        line = line.removeprefix(q).removesuffix(q).strip()
    line = line.removeprefix("#").strip().removeprefix("Run with:").strip()
    try:
        argv = shlex.split(line, comments=True)
    except ValueError:
        return None
    if not argv or argv[0] not in RUNNERS or any(t in {"&&", "||", ";", "|"} for t in argv):
        return None
    if argv[0] == "python3":
        return argv, Path(root)
    # The folder the file's own path in the command is relative to: test_x.py from its folder, scripts/test_x.py
    # from the one above.
    path = Path(path).resolve()
    for arg in reversed(argv):
        rel = arg.removeprefix("./")
        if rel.endswith(".py") and path.as_posix().endswith("/" + rel):
            return argv, Path(path.as_posix()[: -len(rel) - 1])
    return argv, path.parent


def clean_env(env=None, threads=None):
    """The environment without what a local Python distribution sets for its own geo libraries: the wheels bring
    their own PROJ and GDAL data, and an older proj.db or a PYTHONPATH from outside changes what a test sees."""
    env = dict(os.environ if env is None else env)
    env = {k: v for k, v in env.items() if not k.startswith(("PROJ_", "GDAL_", "CONDA_")) and k != "PYTHONPATH"}
    if threads:
        env.update(dict.fromkeys(THREAD_VARS, str(threads)))
    return env


def _files(roots, root):
    for r in roots:
        for p in sorted((Path(root) / r).rglob("test_*.py")):
            if not SKIP & set(p.relative_to(root).parts):
                yield p


def plan(roots, root=ROOT):
    """One job per file that names its command, and one job for all the rest."""
    jobs, rest = [], []
    for p in _files(roots or DEFAULT_ROOTS, root):
        rel = p.relative_to(root).as_posix()
        d = declared(p, root)
        if d:
            jobs.append({"argv": d[0], "cwd": d[1], "files": [rel]})
        else:
            rest.append(rel)
    if rest:
        jobs.append({"argv": ["uvx", "--python", "3.12", "--with-requirements", LOCK, "pytest", "-q", *rest],
                     "cwd": Path(root), "files": rest})
    return jobs


def _run(job, threads=1):
    t = time.time()
    r = subprocess.run([*job["argv"], *(["-p", "no:cacheprovider"] if "pytest" in job["argv"] else [])],
                       cwd=job["cwd"], capture_output=True, text=True, env=clean_env(threads=threads))
    return job, r.returncode, r.stdout + r.stderr, time.time() - t


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("roots", nargs="*")
    a.add_argument("--jobs", type=int, default=4)
    a.add_argument("--threads", type=int, default=1, help="threads per job for the numeric libraries")
    a.add_argument("--list", action="store_true", help="print the commands and exit")
    a = a.parse_args()
    jobs = plan(a.roots)
    if a.list:
        for j in jobs:
            print(f"({j['cwd'].relative_to(ROOT).as_posix() or '.'}) {shlex.join(j['argv'])}")
        return 0
    failed = []
    with ThreadPoolExecutor(a.jobs) as ex:
        for job, code, out, sec in ex.map(lambda j: _run(j, a.threads), jobs):
            name = job["files"][0] if len(job["files"]) == 1 else f"{len(job['files'])} files under the lock"
            print(f"{'ok  ' if code == 0 else 'FAIL'} {sec:6.1f}s {name}", flush=True)
            if code:
                failed.append(name)
                print("\n".join("    " + l for l in out.rstrip().splitlines()[-30:]), flush=True)
    print(f"{len(jobs) - len(failed)} of {len(jobs)} jobs passed")
    for f in failed:
        print("failed:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
