"""Summaries that the report reads: the staged gates side by side, the falsification (F1, F2), the prior
sensitivity (F3) and the value of extra data (VOI). Every number in report.md comes from these files.

From repository root:
    python3 projects/_bear/akita-bear-latent-observation-model/scripts/summarise.py \
      projects/_bear/akita-bear-latent-observation-model/outputs \
      artifacts/_bear/akita-bear-latent-observation-model/sim
"""

import argparse
import json
from pathlib import Path

import gate as gt

KEYS = ("S1_correct", "S2_correct", "S3_false_bear", "S5_false_bear", "S4_correct", "converged_share")
VOI_SCEN = ("S1", "S2", "S3", "S5")


def stages(gates):
    out = {k: {"gate_passed": g["gate_passed"], **{x: g["default"][x] for x in KEYS},
               "detect_counts": g["default"]["detect_counts"]} for k, g in gates.items()}
    if "2" in gates and "3" in gates:
        out["change_3_minus_2"] = {x: round(gates["3"]["default"][x] - gates["2"]["default"][x], 6) for x in KEYS}
    out["any_passed"] = any(g["gate_passed"] for g in gates.values())
    return out


def falsification(real, cv, f1):
    lam = real["models"]["L2"]["params"]["lam_E"]
    sh = f1["shuffles"]
    sl = [s["lam_E"]["mean"] for s in sh]
    out = {"F2": {"real_lam_E": lam, "shuffled_lam_E_mean": sl, "n_shuffles": len(sh),
                  "shuffled_lam_E_mean_below_real_lo90": sum(m < lam["lo90"] for m in sl),
                  "shuffled_lam_E_mean_max": max(sl), "shuffled_lam_E_mean_median": sorted(sl)[len(sl) // 2]}}
    for w in ("E", "Y"):
        key = f"{w}: L2 - L0H"
        g = [s["gains"][key]["sum"] for s in sh]
        out.setdefault("F1", {})
        out["F1"][f"real_{w}_gain"] = cv["gains"][key]["sum"]
        out["F1"][f"shuffled_{w}_gain"] = g
        out["F1"][f"shuffled_{w}_gain_max"] = max(g)
        out["F1"][f"shuffled_{w}_gain_min"] = min(g)
        out["F1"][f"shuffles_with_{w}_gain_above_real"] = sum(x > cv["gains"][key]["sum"] for x in g)
    return out


def sign(x):
    return (x > 0) - (x < 0)


def call(g):
    """+1 / -1 when the 90% interval excludes zero on that side, else 0 (the verdict rule of the cross-source check)."""
    return 1 if g["lo90"] > 0 else -1 if g["hi90"] < 0 else 0


def prior_sensitivity(full_d, full_w, cv_d, cv_w):
    params = {}
    for m, row in full_d["models"].items():
        if m not in full_w["models"]:
            continue
        params[m] = {k: {"default": v, "wide": full_w["models"][m]["params"][k],
                         "same_sign": sign(v["mean"]) == sign(full_w["models"][m]["params"][k]["mean"])}
                     for k, v in row["params"].items() if k in full_w["models"][m]["params"]}
    gains = {k: {"default": v, "wide": cv_w["gains"][k], "same_sign": sign(v["sum"]) == sign(cv_w["gains"][k]["sum"]),
                 "same_call": call(v) == call(cv_w["gains"][k])}
             for k, v in cv_d["gains"].items() if k in cv_w["gains"]}
    flat = [x["same_sign"] for p in params.values() for x in p.values()] + [x["same_sign"] for x in gains.values()]
    return {"params": params, "gains": gains, "all_same_sign": all(flat),
            "all_same_call": all(x["same_call"] for x in gains.values())}


def voi_rates(rows):
    v = {"S1_correct": gt.rate(rows["S1"], lambda r: r["T_B"]["detect"] == 1 and r["T_R"]["detect"] == 0),
         "S2_correct": gt.rate(rows["S2"], lambda r: r["T_R"]["detect"] == 1 and r["T_B"]["detect"] == 0),
         "S3_false_bear": gt.fail_rate(rows["S3"], lambda r: r["T_B"]["detect"] != 0),
         "S5_false_bear": gt.fail_rate(rows["S5"], lambda r: r["T_B"]["detect"] != 0),
         "converged_share": sum(r["converged"] for s in VOI_SCEN for r in rows[s]) / sum(len(rows[s]) for s in VOI_SCEN),
         "n_per_scenario": {s: len(rows[s]) for s in VOI_SCEN}}
    v["S1S2_correct_mean"] = (v["S1_correct"] + v["S2_correct"]) / 2
    return v


def voi(base, extras, seeds=10):
    b = voi_rates({s: [r for r in base[s] if r["seed"] < seeds] for s in VOI_SCEN})
    out = {"baseline": b, "seeds": seeds}
    for name, rows in extras.items():
        v = voi_rates({s: [r for r in rows[s] if r["seed"] < seeds] for s in VOI_SCEN})
        v["gain_S1S2_correct"] = round(v["S1S2_correct_mean"] - b["S1S2_correct_mean"], 6)
        out[name] = v
    return out


def load_rows(simdir, prefix):
    return {s: [json.loads(x) for x in (Path(simdir) / f"{prefix}_{s}.jsonl").read_text(encoding="utf-8").splitlines()]
            for s in VOI_SCEN if (Path(simdir) / f"{prefix}_{s}.jsonl").exists()}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("outputs", type=Path)
    a.add_argument("simdir", type=Path)
    a.add_argument("--voi", action="store_true", help="also summarise the VOI runs (needs every voi_* file)")
    args = a.parse_args()
    o = args.outputs

    def rd(n):
        return json.loads((o / n).read_text(encoding="utf-8"))

    res = {"stages": stages({"2a": rd("identifiability_gate_L3.json"), "2": rd("identifiability_gate_stage2.json"),
                             "3": rd("identifiability_gate_stage3.json")}),
           "falsification": falsification(rd("real_full_default.json"), rd("real_cv_default.json"),
                                          rd("real_f1_shuffle.json")),
           "prior_sensitivity": prior_sensitivity(rd("real_full_default.json"), rd("real_full_wide.json"),
                                                  rd("real_cv_default.json"), rd("real_cv_wide.json"))}
    json.dump(res, open(o / "summary_gates_falsification.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: res["stages"][k] for k in ("change_3_minus_2", "any_passed")}, indent=1))
    print(json.dumps({k: v for k, v in res["falsification"]["F2"].items() if k != "shuffled_lam_E_mean"}, indent=1))
    print("F3 all same sign:", res["prior_sensitivity"]["all_same_sign"], "same call:",
          res["prior_sensitivity"]["all_same_call"])
    if args.voi:
        extras = {v: load_rows(args.simdir, f"voi_{v}") for v in ("V1", "V2", "V3", "V4", "V5", "V6")}
        r = voi(load_rows(args.simdir, "base_default"), extras)
        json.dump(r, open(o / "voi_summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(json.dumps({k: (v if k == "seeds" else {x: v[x] for x in v if x != "n_per_scenario"}) for k, v in r.items()},
                         indent=1))


if __name__ == "__main__":
    main()
