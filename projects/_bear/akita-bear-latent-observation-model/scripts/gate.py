"""The identifiability gate (EXPERIMENT_PLAN.md) from the synthetic fits. A fit that did not converge counts as a
failure of whatever it was meant to show (it is never dropped).

    G1  S1: T_B detected with the right sign and T_R not detected, in >= 80% of seeds
    G2  S2: T_R detected with the right sign and T_B not detected, in >= 80%
    G3  S3 and S5: T_B detected (or the fit failed) in <= 20%
    G4  S4: T_B and T_R both detected with the right signs, in >= 80%
    G5  coverage of the 90% interval of T_B over all scenarios and seeds >= 80%
    G6  with the wide prior, G1-G4 give the same verdicts and the per-seed T_B call agrees in >= 80%
The secondary S_B gate: S1 right sign >= 80%; S2, S3, S5 wrong detection <= 20%; agreement under the wide prior >= 80%.

From repository root:
    python3 projects/_bear/akita-bear-latent-observation-model/scripts/gate.py \
      artifacts/_bear/akita-bear-latent-observation-model/sim base \
      projects/_bear/akita-bear-latent-observation-model/outputs/identifiability_gate.json
"""

import argparse
import json
from pathlib import Path

SCEN = ("S1", "S2", "S3", "S4", "S5")
PASS, FAIL_MAX = 0.8, 0.2


def load(simdir, prefix, prior):
    rows = {}
    for s in SCEN:
        p = Path(simdir) / f"{prefix}_{prior}_{s}.jsonl"
        rows[s] = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return rows


def rate(rows, ok):
    return sum(1 for r in rows if r["converged"] and ok(r)) / len(rows) if rows else float("nan")


def fail_rate(rows, bad):
    return sum(1 for r in rows if (not r["converged"]) or bad(r)) / len(rows) if rows else float("nan")


def verdicts(rows):
    out = {}
    out["S1_correct"] = rate(rows["S1"], lambda r: r["T_B"]["detect"] == 1 and r["T_R"]["detect"] == 0)
    out["S2_correct"] = rate(rows["S2"], lambda r: r["T_R"]["detect"] == 1 and r["T_B"]["detect"] == 0)
    out["S3_false_bear"] = fail_rate(rows["S3"], lambda r: r["T_B"]["detect"] != 0)
    out["S5_false_bear"] = fail_rate(rows["S5"], lambda r: r["T_B"]["detect"] != 0)
    out["S4_correct"] = rate(rows["S4"], lambda r: r["T_B"]["detect"] == 1 and r["T_R"]["detect"] == 1)
    allr = [r for s in SCEN for r in rows[s]]
    out["T_B_coverage"] = rate(allr, lambda r: r["T_B"]["covered"])
    out["converged_share"] = sum(r["converged"] for r in allr) / len(allr) if allr else float("nan")
    out["n_fits"] = len(allr)
    out["G1"] = out["S1_correct"] >= PASS
    out["G2"] = out["S2_correct"] >= PASS
    out["G3"] = out["S3_false_bear"] <= FAIL_MAX and out["S5_false_bear"] <= FAIL_MAX
    out["G4"] = out["S4_correct"] >= PASS
    out["G5"] = out["T_B_coverage"] >= PASS
    out["S_B_S1_right"] = rate(rows["S1"], lambda r: r["S_B"]["detect"] == -1)
    out["S_B_false"] = {s: fail_rate(rows[s], lambda r: r["S_B"]["detect"] != 0) for s in ("S2", "S3", "S5")}
    out["detect_counts"] = {s: {k: {str(v): sum(1 for r in rows[s] if r[k]["detect"] == v) for v in (-1, 0, 1)}
                                for k in ("T_B", "T_R", "S_B")} for s in SCEN}
    return out


def agreement(a, b, key):
    pairs = [(x[key]["detect"], y[key]["detect"]) for s in SCEN
             for x, y in zip(sorted(a[s], key=lambda r: r["seed"]), sorted(b[s], key=lambda r: r["seed"]))]
    return sum(p == q for p, q in pairs) / len(pairs) if pairs else float("nan")


def gate(default, wide):
    vd, vw = verdicts(default), verdicts(wide)
    agree_B = agreement(default, wide, "T_B")
    agree_S = agreement(default, wide, "S_B")
    g6 = all(vd[g] == vw[g] for g in ("G1", "G2", "G3", "G4")) and agree_B >= PASS
    passed = all(vd[g] for g in ("G1", "G2", "G3", "G4", "G5")) and g6
    s_b = (vd["S_B_S1_right"] >= PASS and all(v <= FAIL_MAX for v in vd["S_B_false"].values()) and agree_S >= PASS)
    return {"default": vd, "wide": vw, "agreement_T_B": agree_B, "agreement_S_B": agree_S, "G6": g6,
            "gate_passed": passed, "secondary_S_B_passed": s_b,
            "rule": "dynamic bear inference on real data only if gate_passed"}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("simdir", type=Path)
    a.add_argument("prefix")
    a.add_argument("out", type=Path)
    args = a.parse_args()
    res = gate(load(args.simdir, args.prefix, "default"), load(args.simdir, args.prefix, "wide"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
