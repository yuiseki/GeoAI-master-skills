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
DENSE_STAGE = {"2": ("a", "delta", "a_E", "lam_K", "sr", "sw", "phi"),
               "3": ("a", "tau", "a_E", "lam_K", "sr", "s", "kappa", "phi")}
WARMUP, SAMPLES = 1000, 1000
SUMMARY = Path(__file__).resolve().parents[1] / "outputs/inputs_summary.json"


def targets():
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return {"E6": s["core_E6_rate"], "E7": s["core_E7_rate"], "count": s["core_mean_count"]["2023"]}


def converged(diag):
    return diag["max_rhat"] <= 1.05 and diag["divergent_share"] <= 0.01


def one_stage(data, stage, scenario, seed, prior):
    """Stage 1 (static shared L2 on static S5 data), 2 (epoch states) or 3 (OU transition) on OU-background data."""
    tr = sm.truth(data, scenario, seed, targets(), ou=stage != "1")
    sim, _ = sm.simulate(data, tr, seed)
    t0 = time.time()
    if stage == "1":
        s, diag = lt.fit(lt.model_shared, sim, seed=seed, warmup=WARMUP, samples=SAMPLES, use_H=True, prior=prior)
        row = {"stage": stage, "scenario": scenario, "seed": seed, "prior": prior, **diag, "converged": converged(diag),
               "corr_b": float(np.corrcoef(s["b"].mean(0), tr["b"])[0, 1]),
               "covered": {k: bool(lt.interval(s[k])[0] <= sm.TRUE[k] <= lt.interval(s[k])[1])
                           for k in ("lam_E", "lam_K", "c_E", "c_K")}}
        row["seconds"] = round(time.time() - t0, 1)
        return row
    model = lt.model_epoch if stage == "2" else lt.model_ou
    s, diag = lt.fit(model, sim, seed=seed, warmup=WARMUP, samples=SAMPLES, prior=prior, dense=DENSE_STAGE[stage])
    est, dB = lt.estimands_states(s, sim)
    row = {"stage": stage, "scenario": scenario, "seed": seed, "prior": prior, "seconds": round(time.time() - t0, 1),
           **diag, "converged": converged(diag)}
    for k in ("T_B", "T_R", "S_B"):
        lo, hi = lt.interval(est[k])
        row[k] = {"true": tr[k], "mean": float(est[k].mean()), "lo90": lo, "hi90": hi,
                  "detect": lt.detect(est[k]), "covered": bool(lo <= tr[k] <= hi)}
    row["P_B"] = float(np.corrcoef(dB - dB.mean(), tr["dB"] - tr["dB"].mean())[0, 1])
    if stage == "3":
        klo, khi = lt.interval(s["kappa"])
        plo, phi_ = lt.interval(s["phi_1y"])
        row["kappa"] = {"mean": float(s["kappa"].mean()), "lo90": klo, "hi90": khi,
                        "covered": bool(klo <= sm.OU_KAPPA <= khi)}
        row["phi_1y_width"] = phi_ - plo
    return row


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
    a.add_argument("--stage", default="2a", choices=["2a", "1", "2", "3"],
                   help="2a: the original L3 gate; 1, 2, 3: the staged gates (plan change 2026-10-31)")
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
            if args.stage == "2a":
                row = one(data, args.scenario, seed, args.prior, args.extra)
            else:
                row = one_stage(data, args.stage, args.scenario, seed, args.prior)
            f.write(json.dumps(row) + "\n")
            f.flush()
            if "T_B" in row:
                print(args.scenario, seed, row["converged"], {k: (row[k]["detect"], round(row[k]["mean"], 3), row[k]["covered"])
                                                              for k in ("T_B", "T_R", "S_B")}, row["seconds"], flush=True)
            else:
                print(args.scenario, seed, row["converged"], round(row["corr_b"], 3), row["covered"], flush=True)


if __name__ == "__main__":
    main()
