"""Trigger test: does an agent read the skill and the reference a request needs, and leave the others alone?

The analysis evals (evals/tasks) grade whether an agent reaches the right answer, which takes a full run per task.
This measures one step before that, cheaply and many times: given only a request, which SKILL.md and
references/*.md the agent opens. Cases are in trigger_cases.yaml (explicit, implicit, scope, negative).

Each case gets a fresh workdir (prepare_workdir.py, so no evals/ on its disk), the prompt plus SUFFIX, and one run
of an agent in Docker: OpenCode (run_opencode_docker.sh), Codex (run_codex_docker.sh) or the Gemini CLI
(run_gemini_docker.sh), chosen with --agent; or Claude Code on the host (run_claude_local.sh: no user settings, no
CLAUDE.md unless --context gives one, its workdir outside OUT_DIR under EVAL_CLAUDE_WORK_BASE, default /tmp/trigger-claude). What counts as read: a file tool on a skill file (OpenCode's `read`, the
Gemini CLI's read_file and view_file), OpenCode's `skill` tool (it loads the SKILL.md), or a shell command that
names one (cat, sed, head, grep on the file; Codex reads only this way), also after the shell expands
braces, a for loop or a glob within one skill (cat references/*.md, against the files at the pinned revision). A directory listing does not count, nor does
a name in the agent's text.
Reading a reference counts as reading its skill.

Verdicts: PASS (every expect read, no forbid read), FAIL, ERROR (the run failed: a non-zero exit other than the
time limit 124, an error event from the provider, or no event at all: the provider can hang until the time limit
without answering). An ERROR is not graded: run the case again (--retry-errors). A run cut off
by the time limit is graded on what it had read. When a run's stderr shows the provider's usage limit, the whole run
stops (exit 3) instead of waiting the time limit on every remaining case.

    python3 evals/trigger.py run OUT_DIR [--agent opencode|codex|gemini|claude] [--model M] [--effort E]
        [--context CLAUDE_MD]
        [--cases evals/trigger_cases.yaml] [--only ID ...] [--minutes N] [--repeats N] [--retry-errors]
    python3 evals/trigger.py judge OUT_DIR       # re-grade saved logs
OUT_DIR is one condition. Its first run writes manifest.json: the revision of the skills and the cases (each workdir
is made from it, not from HEAD, and the cases are read from it), the agent, model and effort, the Docker image id,
the CLI's version, the runner's hash and the time limit. Resuming or --retry-errors under anything different is
refused with what changed. It gets one folder per case and run (id/r1/: prompt.md, agent.json, log (stdout),
stderr, exit), summary.tsv (one row per run) and
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


_BRACE = re.compile(r"([^\s{}'\"]*)\{([^{}\s]*,[^{}\s]*)\}([^\s{}'\"]*)")
_FOR = re.compile(r"\bfor\s+(\w+)\s+in\s+([^;]+?)\s*;\s*do\b(.*?)\bdone\b", re.S)


_GLOB = re.compile(r"(\.agents/skills/([A-Za-z0-9_-]+)/[^\s'\";|&<>]*[*?\[][^\s'\";|&<>]*)")
_LISTS = {"ls", "find", "stat", "tree", "du", "file"}


def _globs(text, files):
    """File names a glob within one skill matches among the skill files at the run's revision (files).
    Not for a listing (ls, find) or a wildcard in the skill's name, which searches across skills."""
    out = []
    for seg in re.split(r"&&|\|\||[;|\n]", text):
        words = [w.strip("'\"(") for w in seg.split()]
        while words and (re.fullmatch(r"(/\S*/)?(ba)?sh|-l?c|", words[0])):     # Codex's /bin/bash -lc '...'
            words = words[1:]
        if not words or words[0] in _LISTS:
            continue
        for pat, _skill in _GLOB.findall(seg):
            rx = re.compile(re.escape(pat).replace(r"\*", "[^/]*").replace(r"\?", "[^/]") + "$")
            out += [f for f in files if rx.match(f)]
    return out


def _shell(command, files=()):
    """A shell command with brace expansion, simple for loops and globs within one skill written out, so files
    named only after the shell expands them are seen: cat .agents/skills/{a,b}/SKILL.md,
    for s in a b; do cat .../$s/SKILL.md; done, cat .agents/skills/a/references/*.md (globs need files, the
    skill files at the run's revision)."""
    text, n = command, 0
    while n < 20 and _BRACE.search(text):
        text = _BRACE.sub(lambda m: " ".join(m[1] + x + m[3] for x in m[2].split(",")), text)
        n += 1
    out = [text]
    for var, words, body in _FOR.findall(text):
        for w in words.split():
            out.append(re.sub(r"\$\{?" + var + r"\b\}?", w.strip("'\""), body))
    if files:
        out += _globs("\n".join(out), files)
    return "\n".join(out)


# Tools of the Gemini CLI (agy) that read a file or run a command; list_dir and find_by_name only list.
_AGY_READS = {"read_file", "view_file", "run_command", "grep_search"}


def reads(log_text, files=()):
    """Skills and references the agent read, from the JSON events of any of the four agents: OpenCode
    (`opencode run --format json`), Codex (`codex exec --json`), the Gemini CLI (`agy --output-format
    stream-json`) and Claude Code (`claude -p --output-format stream-json`; Glob only lists). The event shapes do not overlap, so a log is read without being told which agent wrote it.
    files: the skill files at the run's revision, to expand globs (_shell)."""
    got = set()
    for line in log_text.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if not isinstance(j, dict):
            continue
        if j.get("type") == "tool_use":                                     # OpenCode
            part = j.get("part", {})
            inp = part.get("state", {}).get("input") or {}
            if part.get("tool") == "read":
                got |= _items(str(inp.get("filePath", "")))
            elif part.get("tool") == "skill" and re.fullmatch(r"[A-Za-z0-9_-]+", str(inp.get("name", ""))):
                got.add(inp["name"])
            elif part.get("tool") == "bash":
                got |= _items(_shell(str(inp.get("command", "")), files))
        elif j.get("type") == "item.completed":                             # Codex: it reads through the shell
            item = j.get("item") or {}
            if item.get("type") == "command_execution":
                got |= _items(_shell(str(item.get("command", "")), files))
        elif j.get("type") == "assistant":                                  # Claude Code
            for c in (j.get("message") or {}).get("content") or []:
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue
                inp = c.get("input") or {}
                if c.get("name") == "Read":
                    got |= _items(str(inp.get("file_path", "")))
                elif c.get("name") == "Grep":
                    got |= _items(str(inp.get("path", "")))
                elif c.get("name") == "Bash":
                    got |= _items(_shell(str(inp.get("command", "")), files))
        elif j.get("event") == "step_update":                               # Gemini CLI
            st = j.get("step_update") or {}
            if st.get("step_type") == "tool" and st.get("state") == "DONE" and st.get("tool_name") in _AGY_READS:
                params = (st.get("tool_info") or {}).get("parameters") or {}
                got |= _items(_shell(" ".join(str(v) for v in params.values()), files))
    return got


def error_event(log_text):
    """The provider or the agent reported a failed run. Codex's "Reconnecting" errors are retries, not a failure:
    only turn.failed counts."""
    for line in log_text.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if not isinstance(j, dict):
            continue
        if j.get("type") == "error" and "error" in j:                       # OpenCode
            return True
        if j.get("type") == "turn.failed":                                  # Codex
            return True
        if j.get("event") == "result" and (j.get("result") or {}).get("status") != "SUCCESS":   # Gemini CLI
            return True
        if j.get("type") == "result" and (j.get("is_error") or j.get("subtype") != "success"):   # Claude Code
            return True
    return False


def silent(log_text):
    """No JSON event at all: the provider never answered, so the agent did nothing to grade."""
    for line in log_text.splitlines():
        try:
            json.loads(line)
            return False
        except ValueError:
            continue
    return True


def usage_limited(stderr_text, log_text=""):
    """The provider refused for its usage limit. OpenCode retries this until the time limit and writes nothing to
    stdout, so every later run would also wait the full time for nothing. Claude Code says so in its result event."""
    if any("level=ERROR" in line and re.search(r"usage limit reached|rate limit", line, re.I)
           for line in stderr_text.splitlines()):
        return True
    for line in log_text.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if isinstance(j, dict) and j.get("type") == "result" and j.get("is_error") and \
                re.search(r"usage limit|rate limit", str(j.get("result", "")), re.I):
            return True
    return False


def judge(case, read, exit_code, error_event=False, silent=False):
    if error_event or silent or exit_code not in (0, 124):
        return {"verdict": "ERROR", "missing": [], "forbidden": []}
    missing = [x for x in case.get("expect", []) if x not in read]
    forbidden = [x for x in case.get("forbid", []) if x in read]
    return {"verdict": "FAIL" if missing or forbidden else "PASS", "missing": missing, "forbidden": forbidden}


def load_cases(path):
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


CASES = "evals/trigger_cases.yaml"


def _git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True).stdout


def cases_at(revision, path=CASES):
    """The cases as committed at a revision: the working tree may have moved on since the runs began."""
    import yaml
    return yaml.safe_load(_git("show", f"{revision}:{path}"))


IMAGES = {"opencode": ("geoai-master-skills-evals-opencode", "opencode"),
          "codex": ("geoai-master-skills-evals-codex", "codex"), "gemini": ("geoai-master-skills-evals-gemini", "agy")}
RUNNERS = {"opencode": "run_opencode_docker.sh", "codex": "run_codex_docker.sh", "gemini": "run_gemini_docker.sh",
           "claude": "run_claude_local.sh"}
# What makes two runs comparable. The creation time is recorded but is not a condition.
CONDITIONS = ("revision", "cases", "cases_sha256", "suffix_sha256", "agent", "model", "effort", "image",
              "image_id", "cli_version", "runner_sha256", "minutes", "context_sha256")


def build_manifest(revision, cases, meta, minutes):
    """The conditions of an OUT_DIR, fixed by its first run. The revision is resolved to a full sha."""
    import datetime
    import hashlib
    run = lambda *c: subprocess.run(c, capture_output=True, text=True, check=True).stdout.strip()
    if meta["agent"] == "claude":                    # on the host (run_claude_local.sh): no image
        image, image_id, cli_version = "host", "", run("claude", "--version")
    else:
        image, cli = IMAGES[meta["agent"]]
        image = os.environ.get("EVAL_IMAGE", image)
        image_id = run("docker", "image", "inspect", "--format", "{{.Id}}", image)
        cli_version = run("docker", "run", "--rm", image, cli, "--version").splitlines()[-1]
    return {
        "revision": _git("rev-parse", "--verify", f"{revision}^{{commit}}").strip(),
        "cases": cases,
        "cases_sha256": hashlib.sha256(_git("show", f"{revision}:{cases}").encode()).hexdigest(),
        "suffix_sha256": hashlib.sha256(SUFFIX.encode()).hexdigest(),
        **meta,
        "image": image,
        "image_id": image_id,
        "cli_version": cli_version,
        "runner_sha256": hashlib.sha256((HERE / RUNNERS[meta["agent"]]).read_bytes()).hexdigest(),
        "minutes": minutes,
        "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def manifest_diff(old, new):
    return sorted(k for k in CONDITIONS if old.get(k) != new.get(k))


def prompt_problems(case, names):
    """A prompt may not name a skill or a reference file: finding them is what is measured."""
    return [f"{case['id']} names {n}" for n in sorted(names) if n in case["prompt"]]


# The defaults are the conditions of the earlier evals (evals/results): Codex gpt-6-luna at medium effort, the
# Gemini CLI with gemini-3.8-flash-low (OAuth; the effort is part of the name), OpenCode's free DeepSeek.
DEFAULTS = {"opencode": ("opencode/deepseek-v4.1-flash-free", ""), "codex": ("gpt-6-luna", "medium"),
            "gemini": ("gemini-3.8-flash-low", ""), "claude": ("claude-sonnet-5-5", "")}


def agent_command(agent, model, effort, prompt, work, context=None):
    """The runner command for one run, and the agent, model and effort to record with it. context: a file Claude
    Code gets as CLAUDE.md above its workdir (recorded by its hash; "none" when there is none)."""
    import hashlib
    model = model or DEFAULTS[agent][0]
    effort = effort or DEFAULTS[agent][1]
    if context and agent != "claude":
        raise ValueError("--context is a CLAUDE.md: only Claude Code reads it")
    if agent == "claude":
        cmd = [str(HERE / "run_claude_local.sh"), "--prompt", str(prompt)]
        cmd += ["--context", str(context)] if context else []
        cmd += [str(work)] + (["--effort", effort] if effort else []) + ["--model", model]
        sha = hashlib.sha256(Path(context).read_bytes()).hexdigest() if context else "none"
        return cmd, {"agent": agent, "model": model, "effort": effort, "context_sha256": sha}
    if agent == "codex":
        cmd = [str(HERE / "run_codex_docker.sh"), "--prompt", str(prompt), str(work), "--json",
               "-m", model, "-c", f"model_reasoning_effort={effort}"]
    elif agent == "gemini":
        if effort:
            raise ValueError("with the Gemini CLI the effort is part of the model name (gemini-3.8-flash-low)")
        cmd = [str(HERE / "run_gemini_docker.sh"), "--auth", "oauth", "--prompt", str(prompt), str(work),
               "--model", model]
    elif agent == "opencode":
        if effort:
            raise ValueError("the OpenCode runner takes no effort")
        cmd = [str(HERE / "run_opencode_docker.sh"), "--prompt", str(prompt), str(work)]
    else:
        raise ValueError(agent)
    return cmd, {"agent": agent, "model": model, "effort": effort}


def _run_case(case, out, agent, model, effort, minutes, repeat=1, revision="HEAD", context=None):
    d = out / case["id"] / f"r{repeat}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    work = d / "work"
    if agent == "claude":
        # Claude Code reads every CLAUDE.md above its folder, and OUT_DIR may be under one. Its workdir goes in a
        # folder of its own under EVAL_CLAUDE_WORK_BASE, which run_claude_local.sh checks has none above it.
        import tempfile
        base = Path(os.environ.get("EVAL_CLAUDE_WORK_BASE", "/tmp/trigger-claude"))
        base.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=f"{case['id']}-r{repeat}-", dir=base)) / "work"
    subprocess.run([sys.executable, str(HERE / "prepare_workdir.py"), revision, str(work), "--repo", str(REPO)],
                   check=True, capture_output=True)
    (d / "prompt.md").write_text(case["prompt"] + SUFFIX + "\n", encoding="utf-8")
    cmd, meta = agent_command(agent, model, effort, d / "prompt.md", work, **({"context": context} if context else {}))
    (d / "agent.json").write_text(json.dumps(meta) + "\n")
    env = dict(os.environ, **({"EVAL_MODEL": meta["model"]} if agent == "opencode" else {}))
    with open(d / "log", "w", encoding="utf-8") as log, open(d / "stderr", "w", encoding="utf-8") as err:
        r = subprocess.run(["timeout", f"{minutes}m", *cmd], stdout=log, stderr=err, env=env)
    (d / "exit").write_text(f"{r.returncode}\n")
    shutil.rmtree(work.parent if agent == "claude" else work, ignore_errors=True)
    return usage_limited((d / "stderr").read_text(encoding="utf-8", errors="replace"),
                         (d / "log").read_text(encoding="utf-8", errors="replace"))


def _runs(out, case_id):
    """The run folders of a case: id/r1, id/r2, ... (or id itself, for logs saved before repeats existed)."""
    d = out / case_id
    runs = sorted((x for x in d.glob("r*") if (x / "exit").exists()), key=lambda x: int(x.name[1:]))
    return runs or ([d] if (d / "exit").exists() else [])


def _verdict(case, d):
    text = (d / "log").read_text(encoding="utf-8", errors="replace")
    return judge(case, reads(text), int((d / "exit").read_text().strip()), error_event(text), silent(text))["verdict"]


def _needs_run(out, case, k, retry_errors=False):
    """Whether run k of the case is still to do. With retry_errors, a run in ERROR is moved to id/err/rK-N (kept,
    out of the grade) and run again."""
    d = out / case["id"] / f"r{k}"
    if not (d / "exit").exists():
        return True
    if not retry_errors or _verdict(case, d) != "ERROR":
        return False
    n = 1
    while (out / case["id"] / "err" / f"r{k}-{n}").exists():
        n += 1
    (out / case["id"] / "err").mkdir(exist_ok=True)
    d.rename(out / case["id"] / "err" / f"r{k}-{n}")
    return True


def skill_files(revision):
    """The skill files at a revision, to expand the globs an agent ran (cat references/*.md)."""
    return _git("ls-tree", "-r", "--name-only", revision, ".agents/skills").split()


def grade(out, cases, files=()):
    """summary.tsv: one row per run. cases.tsv: per case, runs passed, runs graded (PASS or FAIL), runs in ERROR.
    files: the skill files at the pinned revision (skill_files), to expand globs."""
    rows, per_case = [], []
    for case in cases:
        verdicts = []
        for d in _runs(out, case["id"]):
            text = (d / "log").read_text(encoding="utf-8", errors="replace")
            got = reads(text, files)
            r = judge(case, got, int((d / "exit").read_text().strip()), error_event(text), silent(text))
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
    p.add_argument("--cases", default=CASES, help="path in the repository, read at the pinned revision")
    p.add_argument("--rev", default="HEAD", help="revision of the skills and cases for a new OUT_DIR (then fixed)")
    p.add_argument("--only", nargs="*")
    p.add_argument("--agent", choices=sorted(DEFAULTS), default="opencode")
    p.add_argument("--model", help="default per agent: " + ", ".join(f"{a} {m}" for a, (m, _) in DEFAULTS.items()))
    p.add_argument("--effort", help="Codex (default medium) and Claude Code (default: claude's own)")
    p.add_argument("--context", help="Claude Code only: a file it gets as CLAUDE.md (e.g. the user's global rules); "
                                     "recorded by its hash")
    p.add_argument("--minutes", type=int, default=10)
    p.add_argument("--repeats", type=int, default=1, help="runs per case (r1, r2, ...); runs already there are kept")
    p.add_argument("--retry-errors", action="store_true", help="run again the runs in ERROR (the old ones go to id/err/)")
    a = p.parse_args()
    out = Path(a.out).resolve()
    if REPO in out.parents or out == REPO:
        sys.exit("OUT_DIR must be outside the repository")
    mf = out / "manifest.json"
    had = json.loads(mf.read_text()) if mf.exists() else None
    if a.cmd == "run":
        meta = agent_command(a.agent, a.model, a.effort, "p", "w", **({"context": a.context} if a.context else {}))[1]
        if had is None and any(out.glob("*/r*/exit")):
            sys.exit(f"{out} has runs but no manifest.json (made before manifests): use a new OUT_DIR")
        now = build_manifest(had["revision"] if had else a.rev, had["cases"] if had else a.cases, meta, a.minutes)
        if had:
            diff = manifest_diff(had, now)
            if diff:
                sys.exit(f"{out} was run under other conditions: " +
                         "; ".join(f"{k}: {had.get(k)} -> {now.get(k)}" for k in diff))
        else:
            out.mkdir(parents=True, exist_ok=True)
            mf.write_text(json.dumps(now, indent=1) + "\n")
            had = now
        print(f"revision {had['revision'][:10]} {meta['agent']} {meta['model']} {meta['effort']} "
              f"{had['cli_version']}", flush=True)
    # The tables always list every case that has runs, from the pinned revision when there is one.
    every = cases_at(had["revision"], had["cases"]) if had else load_cases(REPO / a.cases)
    cases = [c for c in every if not a.only or c["id"] in a.only]
    files = skill_files(had["revision"]) if had else skill_files("HEAD")
    if a.cmd == "run":
        for k in range(1, a.repeats + 1):        # round by round, so a stop half way leaves every case run alike
            for c in cases:
                if not _needs_run(out, c, k, a.retry_errors):
                    continue
                print(f"running {c['id']} r{k}", flush=True)
                if _run_case(c, out, a.agent, a.model, a.effort, a.minutes, k, had["revision"], a.context):
                    print(f"stopped: the provider's usage limit (see {c['id']}/r{k}/stderr); "
                          "run again later with --retry-errors", flush=True)
                    grade(out, every, files)
                    sys.exit(3)
    grade(out, every, files)


if __name__ == "__main__":
    main()
