"""Prepare the working copy an evaluated agent works in, without evals/.

The agent is told to work in a prepared directory instead of cloning the repository, so the rubric,
the tasks and the results under evals/ are never on its disk. `git archive` leaves out what
`.gitattributes` marks export-ignore; the script also deletes evals/ itself, so a missing attribute
cannot leak the answers.

Usage:
    python prepare_workdir.py REV DEST [--baseline] [--repo PATH]
    python prepare_workdir.py REV DEST --task evals/tasks/tasks.md --number 9 \
        --template evals/prompts/agent-task.md

--baseline gives an empty working copy (only projects/), for measuring the agent without the skills.
With --task and --template, the filled prompt is printed after the directory is prepared.
The prompt differs only in the paragraph about the skills (see the {{#SKILLS}} markers in the template).
--prompt-workdir /work puts that path in the prompt, for evals/run_codex_docker.sh.
--table-file NAME also writes the task's ```csv block to DEST/data/NAME (with or without the skills) and adds
a line to the prompt saying where it is. A table only inside the prompt has to be copied out by the agent;
a 300-row table was not, in any of six runs (task 26, 2026-10-17).
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def prepare(repo, rev, dest, baseline):
    repo, dest = Path(repo), Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty; refusing to write into it")
    dest.mkdir(parents=True, exist_ok=True)
    if baseline:
        (dest / "projects").mkdir()
    else:
        archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", rev],
                                 check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
        shutil.rmtree(dest / "evals", ignore_errors=True)
        (dest / "projects").mkdir(exist_ok=True)
    if (dest / "evals").exists():
        raise SystemExit("evals/ is present in the working copy")
    return dest


def extract_task(text, number):
    m = re.search(rf"^## 課題 {number}:.*?(?=^## 課題 |\Z)", text, re.S | re.M)
    if not m:
        raise SystemExit(f"task {number} not found")
    return m.group(0).rstrip() + "\n"


def extract_table(task):
    m = re.search(r"^```csv\n(.*?)^```", task, re.S | re.M)
    if not m:
        raise SystemExit("the task has no ```csv block")
    return m.group(1)


def render_prompt(template, workdir, task, sha, baseline=False):
    """Keep {{#SKILLS}}..{{/SKILLS}} with skills, {{#BASELINE}}..{{/BASELINE}} without; the rest is shared."""
    keep, drop = ("BASELINE", "SKILLS") if baseline else ("SKILLS", "BASELINE")
    template = re.sub(rf"{{{{#{drop}}}}}.*?{{{{/{drop}}}}}", "", template, flags=re.S)
    template = template.replace(f"{{{{#{keep}}}}}", "").replace(f"{{{{/{keep}}}}}", "")
    return (template.replace("{{WORKDIR}}", str(workdir)).replace("{{SHA}}", sha)
            .replace("{{TASK}}", task))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rev")
    p.add_argument("dest")
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    p.add_argument("--task", help="the tasks file")
    p.add_argument("--number", type=int, help="which task in it")
    p.add_argument("--template")
    p.add_argument("--prompt-workdir", help="the path to write into the prompt (default: DEST); "
                   "/work when the agent runs in Docker")
    p.add_argument("--table-file", help="write the task's csv block to DEST/data/NAME and say so in the prompt")
    a = p.parse_args()
    prepare(a.repo, a.rev, a.dest, a.baseline)
    task = extract_task(Path(a.task).read_text(), a.number) if a.task else None
    if a.table_file:
        if task is None:
            raise SystemExit("--table-file needs --task and --number")
        (Path(a.dest) / "data").mkdir(exist_ok=True)
        (Path(a.dest) / "data" / a.table_file).write_text(extract_table(task))
        workdir = a.prompt_workdir or Path(a.dest).resolve()
        task += f"\n上の表と同じ内容のファイルを {workdir}/data/{a.table_file} に置いてある。\n"
    sha = subprocess.run(["git", "-C", a.repo, "rev-parse", "--short", a.rev], check=True,
                         capture_output=True, text=True).stdout.strip()
    print(f"prepared {a.dest} from {sha}{' (baseline, no skills)' if a.baseline else ''}",
          file=sys.stderr)
    if a.task and a.template:
        print(render_prompt(Path(a.template).read_text(), a.prompt_workdir or Path(a.dest).resolve(),
                            task, sha, a.baseline))


if __name__ == "__main__":
    main()
