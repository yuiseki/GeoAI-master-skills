"""Run the identifiability experiment: for each scenario and seed, make synthetic data on the real core meshes, fit
the dynamic model L3 (with any value-of-information stream), and record the 90% intervals of T_B, T_R and S_B, the
detections, the coverage and the convergence. One JSON line per fit; nothing is written for real data.

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-latent-observation-model/scripts uvx --with numpyro==0.22.0 \
      --with jax==0.12.0.1 --with numpy==2.5.4 --with scipy --with pandas --with pyarrow python \
      projects/_bear/akita-bear-latent-observation-model/scripts/identifiability.py \
      artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-latent-observation-model \
      --scenario S1 --seeds 0 20 --prior default --out artifacts/_bear/akita-bear-latent-observation-model/sim/base_default_S1.jsonl
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

import latent as lt
import simulate as sm

DENSE = ("a", "g", "a_E", "lam_K", "sr", "sv", "phi")  # the year effects lie on a ridge (EXPERIMENT_PLAN.md, 計画の変更)
DENSE_V5 = ("a0", "beta_hist", "g", "a_E", "lam_K", "sr", "sv", "phi")
WARMUP, SAMPLES = 1000, 1000
SUMMARY = Path(__file__).resolve().parents[1] / "outputs/inputs_summary.json"


def targets():
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return {"E6": s["core_E6_rate"], "E7": s["core_E7_rate"], "count": s["core_mean_count"]["2023"]}


def converged(diag):
    return diag["max_rhat"] <= 1.05 and diag["divergent_share"] <= 0.01


def one(data, scenario, seed, prior, extra=None):
    tr = sm.truth(data, scenario, seed, targets())
    if extra == "V5":
        tr = sm.history_truth(data, tr)
    sim, ex = sm.simulate(data, tr, seed, extras=(extra,) if extra else ())
    t0 = time.time()
    s, diag = lt.fit(lt.model_shared, sim, seed=seed, warmup=WARMUP, samples=SAMPLES, use_H=True, dynamic=True,
                     prior=prior, extras=ex or None,
                     dense=DENSE_V5 if extra == "V5" else DENSE)
    est = lt.estimands(s, sim)
    row = {"scenario": scenario, "seed": seed, "prior": prior, "extra": extra, "seconds": round(time.time() - t0, 1),
           **diag, "converged": converged(diag)}
    for k in ("T_B", "T_R", "S_B"):
        lo, hi = lt.interval(est[k])
        row[k] = {"true": tr[k], "mean": float(est[k].mean()), "lo90": lo, "hi90": hi,
                  "detect": lt.detect(est[k]), "covered": bool(lo <= tr[k] <= hi)}
    return row


def main():
    import numpyro

    numpyro.set_host_device_count(2)
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("--scenario", required=True, choices=sm.SCENARIOS)
    a.add_argument("--seeds", type=int, nargs=2, required=True, help="first and one past the last")
    a.add_argument("--prior", default="default", choices=list(lt.PRIORS))
    a.add_argument("--extra", default=None, choices=["V1", "V2", "V3", "V4", "V5", "V6"])
    a.add_argument("--out", type=Path, required=True)
    args = a.parse_args()
    meta = json.loads((args.art / "grid.json").read_text(encoding="utf-8"))
    data = sm.load_core(args.work / "mesh/mesh_table.parquet", meta)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.out.exists():
        done = {json.loads(line)["seed"] for line in args.out.read_text(encoding="utf-8").splitlines()}
    with open(args.out, "a", encoding="utf-8") as f:
        for seed in range(*args.seeds):
            if seed in done:
                continue
            row = one(data, args.scenario, seed, args.prior, args.extra)
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(args.scenario, seed, row["converged"], {k: (row[k]["detect"], round(row[k]["mean"], 3), row[k]["covered"])
                                                          for k in ("T_B", "T_R", "S_B")}, row["seconds"], flush=True)


if __name__ == "__main__":
    main()
