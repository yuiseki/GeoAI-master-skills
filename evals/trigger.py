"""Trigger test: does an agent read the skill and the reference a request needs, and leave the others alone?

The analysis evals (evals/tasks) grade whether an agent reaches the right answer, which takes a full run per task.
This measures one step before that, cheaply and many times: given only a request, which SKILL.md and
references/*.md the agent opens. Cases are in trigger_cases.yaml (explicit, implicit, scope, negative).

Each case gets a fresh workdir (prepare_workdir.py, so no evals/ on its disk), the prompt plus SUFFIX, and one run
of evals/run_opencode_docker.sh. What counts as read: a `read` call on a skill file, OpenCode's `skill` tool (it loads the
SKILL.md), or a shell command that names one (cat, sed, head, grep on the file). A directory listing does not count, nor does a name in the agent's text.
Reading a reference counts as reading its skill.

Verdicts: PASS (every expect read, no forbid read), FAIL, ERROR (the run failed: a non-zero exit other than the
time limit 124, or an error event from the provider). An ERROR is not graded: run the case again. A run cut off
by the time limit is graded on what it had read.

    python3 evals/trigger.py run OUT_DIR [--cases evals/trigger_cases.yaml] [--only ID ...] [--model M] [--minutes N] [--repeats N]
    python3 evals/trigger.py judge OUT_DIR       # re-grade saved logs
OUT_DIR gets one folder per case and run (id/r1/: prompt.md, log, exit), summary.tsv (one row per run) and
cases.tsv (per case: runs passed, graded, in error). --repeats N runs each case N times, round by round, and
keeps the runs already there, so a stopped run can be resumed. Keep OUT_DIR outside the repository.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SUFFIX = ("\n\nまだ計算は流さず、データも取りに行かないでください。このリポジトリの中で使う手順を決めるところまで進め、"
          "決めた手順を 5 行以内で答えてください。")
_FILE = re.compile(r"\.agents/skills/([A-Za-z0-9_-]+)/(SKILL\.md|references/[A-Za-z0-9_./-]+?\.md)\b")


def _items(path_text):
    out = set()
    for skill, rest in _FILE.findall(path_text):
        out.add(skill)
        if rest != "SKILL.md":
            out.add(f"{skill}/{rest}")
    return out


def reads(log_text):
    """Skills and references the agent read, from the JSON events of `opencode run --format json`."""
    got = set()
    for line in log_text.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get("type") != "tool_use":
            continue
        part = j.get("part", {})
        inp = part.get("state", {}).get("input") or {}
        if part.get("tool") == "read":
            got |= _items(str(inp.get("filePath", "")))
        elif part.get("tool") == "skill" and re.fullmatch(r"[A-Za-z0-9_-]+", str(inp.get("name", ""))):
            got.add(inp["name"])
        elif part.get("tool") == "bash":
            got |= _items(str(inp.get("command", "")))
    return got


def error_event(log_text):
    for line in log_text.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get("type") == "error":
            return True
    return False


def judge(case, read, exit_code, error_event=False):
    if error_event or exit_code not in (0, 124):
        return {"verdict": "ERROR", "missing": [], "forbidden": []}
    missing = [x for x in case.get("expect", []) if x not in read]
    forbidden = [x for x in case.get("forbid", []) if x in read]
    return {"verdict": "FAIL" if missing or forbidden else "PASS", "missing": missing, "forbidden": forbidden}


def load_cases(path):
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def prompt_problems(case, names):
    """A prompt may not name a skill or a reference file: finding them is what is measured."""
    return [f"{case['id']} names {n}" for n in sorted(names) if n in case["prompt"]]


def _run_case(case, out, model, minutes, repeat=1):
    d = out / case["id"] / f"r{repeat}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    work = d / "work"
    subprocess.run([sys.executable, str(HERE / "prepare_workdir.py"), "HEAD", str(work), "--repo", str(REPO)],
                   check=True, capture_output=True)
    (d / "prompt.md").write_text(case["prompt"] + SUFFIX + "\n", encoding="utf-8")
    env = dict(os.environ, **({"EVAL_MODEL": model} if model else {}))
    with open(d / "log", "w", encoding="utf-8") as log:
        r = subprocess.run(["timeout", f"{minutes}m", str(HERE / "run_opencode_docker.sh"), "--prompt",
                            str(d / "prompt.md"), str(work)], stdout=log, stderr=subprocess.DEVNULL, env=env)
    (d / "exit").write_text(f"{r.returncode}\n")
    shutil.rmtree(work, ignore_errors=True)


def _runs(out, case_id):
    """The run folders of a case: id/r1, id/r2, ... (or id itself, for logs saved before repeats existed)."""
    d = out / case_id
    runs = sorted((x for x in d.glob("r*") if (x / "exit").exists()), key=lambda x: int(x.name[1:]))
    return runs or ([d] if (d / "exit").exists() else [])


def grade(out, cases):
    """summary.tsv: one row per run. cases.tsv: per case, runs passed, runs graded (PASS or FAIL), runs in ERROR."""
    rows, per_case = [], []
    for case in cases:
        verdicts = []
        for d in _runs(out, case["id"]):
            text = (d / "log").read_text(encoding="utf-8", errors="replace")
            got = reads(text)
            r = judge(case, got, int((d / "exit").read_text().strip()), error_event(text))
            verdicts.append(r["verdict"])
            rows.append([case["id"], case["kind"], r["verdict"], " ".join(r["missing"]), " ".join(r["forbidden"]),
                         " ".join(sorted(got)), d.name])
        if verdicts:
            per_case.append([case["id"], case["kind"], str(verdicts.count("PASS")),
                             str(sum(v != "ERROR" for v in verdicts)), str(verdicts.count("ERROR"))])
    with open(out / "summary.tsv", "w", encoding="utf-8") as f:
        f.write("id\tkind\tverdict\tmissing\tforbidden\tread\trun\n")
        for row in rows:
            f.write("\t".join(row) + "\n")
    with open(out / "cases.tsv", "w", encoding="utf-8") as f:
        f.write("id\tkind\tpassed\tgraded\terrors\n")
        for row in per_case:
            f.write("\t".join(row) + "\n")
    for row in per_case:
        print("\t".join(row))
    return rows, per_case


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["run", "judge"])
    p.add_argument("out")
    p.add_argument("--cases", default=str(HERE / "trigger_cases.yaml"))
    p.add_argument("--only", nargs="*")
    p.add_argument("--model")
    p.add_argument("--minutes", type=int, default=10)
    p.add_argument("--repeats", type=int, default=1, help="runs per case (r1, r2, ...); runs already there are kept")
    a = p.parse_args()
    out = Path(a.out).resolve()
    if REPO in out.parents or out == REPO:
        sys.exit("OUT_DIR must be outside the repository")
    cases = [c for c in load_cases(a.cases) if not a.only or c["id"] in a.only]
    if a.cmd == "run":
        for k in range(1, a.repeats + 1):        # round by round, so a stop half way leaves every case run alike
            for c in cases:
                if (out / c["id"] / f"r{k}" / "exit").exists():
                    continue
                print(f"running {c['id']} r{k}", flush=True)
                _run_case(c, out, a.model, a.minutes, k)
    grade(out, cases)


if __name__ == "__main__":
    main()
