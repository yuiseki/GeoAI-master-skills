"""How much work a run took, read from the agent's own log: tokens, tool calls, failed calls, wall minutes.

A run directory holds prompt.md, log (the agent's output) and exit (written when it ended), as the
matrix scripts leave them. Codex writes a text log; agy (Gemini eval) writes stream-json.
Compare tokens only within one agent: the two CLIs count them differently.

    python evals/effort.py RUN_DIR [RUN_DIR ...]      # one TSV row per run
"""

import json
import re
import sys
from pathlib import Path

FIELDS = ("run", "agent", "exit", "tokens", "calls", "failed_calls", "minutes")


def parse_codex(text):
    tokens = re.findall(r"^tokens used\n([\d,]+)$", text, flags=re.M)
    return {
        "tokens": int(tokens[-1].replace(",", "")) if tokens else None,
        "calls": len(re.findall(r"^exec$", text, flags=re.M)),
        "failed_calls": len(re.findall(r"^ exited [1-9]\d* in ", text, flags=re.M)),
    }


def parse_agy(text):
    tools, errors, tokens = set(), set(), None
    for line in text.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get("event") == "step_update":
            s = j["step_update"]
            if s.get("step_type") == "tool":
                tools.add(s["step_index"])
                if s.get("state") == "ERROR":
                    errors.add(s["step_index"])
        elif j.get("event") == "result":
            tokens = (j["result"].get("usage") or {}).get("total_tokens")
    return {"tokens": tokens, "calls": len(tools), "failed_calls": len(errors)}


def run_effort(run_dir):
    d = Path(run_dir)
    text = (d / "log").read_text(errors="replace")
    agent = "agy" if text.lstrip().startswith('{"event"') else "codex"
    e = (parse_agy if agent == "agy" else parse_codex)(text)
    done = d / "exit"
    minutes = round((done.stat().st_mtime - (d / "prompt.md").stat().st_mtime) / 60, 1) if done.exists() else None
    return {"run": d.name, "agent": agent, "exit": done.read_text().strip() if done.exists() else None,
            **e, "minutes": minutes}


if __name__ == "__main__":
    print("\t".join(FIELDS))
    for a in sys.argv[1:]:
        r = run_effort(a)
        print("\t".join("" if r[f] is None else str(r[f]) for f in FIELDS))
