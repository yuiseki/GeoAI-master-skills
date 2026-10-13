"""Re-run an analysis under every combination of changed conditions and see whether a claim holds.

Each --step is a shell command with {name} placeholders. For every combination of the --vary
values, the steps run in order; numbers are pulled from the last step's output by --extract
patterns (NAME=REGEX, the first group is the number), and the --claim, an expression over those
names, is evaluated. A step that fails, or a pattern that finds nothing, stops the run: a missing
number is not a held claim.

Claims may use the extracted names, numbers, + - * /, comparisons, and, or, not, abs, min, max.

Usage:
    python robustness_grid.py \
      --vary table=tmp/a.parquet,tmp/b.parquet --vary scheme=rows,group \
      --step "uvx ... make_folds.py {table} iso3 --scheme {scheme} ... --out tmp/f.parquet" \
      --step "uvx ... compare_models.py {table} iso3 ... --folds-file tmp/f.parquet" \
      --extract "linear=^linear .*r2 ([-0-9.]+)" --extract "hgb=^hgb .*r2 ([-0-9.]+)" \
      --claim "linear > hgb"
"""

import argparse
import ast
import itertools
import re
import subprocess

ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Compare, ast.Lt, ast.LtE, ast.Gt,
    ast.GtE, ast.Eq, ast.NotEq, ast.Name, ast.Load, ast.Constant, ast.Call,
)
ALLOWED_CALLS = {"abs": abs, "min": min, "max": max}


def grid(vary):
    names, values = [], []
    for v in vary:
        name, vals = v.split("=", 1)
        names.append(name)
        values.append(vals.split(","))
    return [dict(zip(names, combo)) for combo in itertools.product(*values)]


def extract(output, patterns):
    vals = {}
    for p in patterns:
        name, regex = p.split("=", 1)
        m = re.search(regex, output, re.MULTILINE)
        if not m:
            raise SystemExit(f"pattern for {name} found nothing in:\n{output[-2000:]}")
        vals[name] = float(m.group(1))
    return vals


def check_claim(claim, values):
    tree = ast.parse(claim, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise SystemExit(f"not allowed in a claim: {type(node).__name__}")
        if isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name) and node.func.id in ALLOWED_CALLS):
            raise SystemExit("only abs, min and max may be called in a claim")
        if isinstance(node, ast.Name) and node.id not in values and node.id not in ALLOWED_CALLS \
                and node.id not in ("True", "False"):
            raise SystemExit(f"{node.id} is not an extracted value")
    env = {"__builtins__": {}, **ALLOWED_CALLS, **values}
    return bool(eval(compile(tree, "<claim>", "eval"), env))  # nodes checked above


def run_grid(steps, combos, patterns, claim, echo=False):
    rows = []
    for vary in combos:
        out = ""
        for step in steps:
            cmd = step.format(**vary)
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit(f"step failed ({r.returncode}) for {vary}: {cmd}\n{r.stderr[-2000:]}")
            out = r.stdout
        values = extract(out, patterns)
        holds = check_claim(claim, values)
        rows.append({"vary": vary, "values": values, "holds": holds})
        if echo:
            print(_line(rows[-1]), flush=True)
    return rows


def _line(row):
    v = "  ".join(f"{k}={x}" for k, x in row["vary"].items())
    n = "  ".join(f"{k} {x:.4g}" for k, x in row["values"].items())
    return f"{'holds ' if row['holds'] else 'FAILS '} {v}  |  {n}"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--vary", action="append", default=[], help="NAME=V1,V2,...")
    p.add_argument("--step", action="append", required=True)
    p.add_argument("--extract", action="append", default=[], help="NAME=REGEX")
    p.add_argument("--claim", required=True)
    a = p.parse_args()
    combos = grid(a.vary)
    print(f"claim: {a.claim}, conditions: {len(combos)}")
    rows = run_grid(a.step, combos, a.extract, a.claim, echo=True)
    held = sum(r["holds"] for r in rows)
    print(f"the claim holds in {held} of {len(rows)} conditions")


if __name__ == "__main__":
    main()
