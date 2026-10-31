"""Real-data fits of the static models (L0, L0H, L1, L2, and L2 with B x H once), the cross-source validation and
the falsification (F1 block shuffle of the Ministry records, F2 the shared fit on the shuffled records).

    full   4 chains x 1,000 + 1,000: diagnostics, the main parameters, posterior predictive checks, and the posterior
           mean and sd of the latent b per mesh (artifacts, derived)
    cv     5 folds of 2nd-order mesh blocks; hide the Ministry records (or the Kumadas counts) of a fold, fit with the
           rest, and score the hidden records by log predictive density per mesh
    f1     cv for L0 and L1 with the Ministry records moved block by block (seeds 0-9), plus the full L1 fit (F2)

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-latent-observation-model/scripts uvx --with numpyro==0.22.0 \
      --with jax==0.12.0.1 --with numpy==2.5.4 --with scipy --with pandas --with pyarrow python \
      projects/_bear/akita-bear-latent-observation-model/scripts/real_models.py full \
      artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-latent-observation-model \
      projects/_bear/akita-bear-latent-observation-model/outputs/real_full_default.json --prior default
"""

import argparse
import json
import time
from functools import partial
from pathlib import Path

import numpy as np

import latent as lt
import simulate as sm

MODELS = {
    "L0": partial(lt.model_independent, use_H=False),
    "L0H": partial(lt.model_independent, use_H=True),
    "L1": partial(lt.model_shared, use_H=False),
    "L2": partial(lt.model_shared, use_H=True),
    "L2x": partial(lt.model_shared, use_H=True, interaction=True),
}
FOLDS = 5
SUB = ("22", "27", "72", "77")


def folds(blocks, k=FOLDS, seed=0):
    u = np.unique(blocks)
    order = np.random.default_rng(seed).permutation(len(u))
    f = np.empty(len(u), int)
    f[order] = np.arange(len(u)) % k
    return f[np.searchsorted(u, blocks)]


def shuffle_env(data, seed):
    """Move the Ministry records of each 2nd-order block to another block, keeping the position in the block.
    A target mesh that has no source mesh gets no record (masked)."""
    codes = data["mesh_code"]
    blocks = np.array([c[:6] for c in codes])
    u = np.unique(blocks)
    perm = dict(zip(u, u[np.random.default_rng(seed).permutation(len(u))]))
    where = {c: i for i, c in enumerate(codes)}
    E = np.zeros_like(data["E"])
    mask = np.zeros_like(data["env_mask"])
    for i, c in enumerate(codes):  # source mesh i goes to perm[block] + same sub-position
        j = where.get(perm[c[:6]] + c[6:])
        if j is not None:
            E[:, j] = data["E"][:, i]
            mask[:, j] = True
    return E, mask


def logmeanexp(x, axis=0):
    m = x.max(axis)
    return m + np.log(np.mean(np.exp(x - m), axis))


def heldout_lpd(model, samples, data, which):
    """Per-mesh log predictive density of the Ministry records (which='E') or the Kumadas counts ('Y')."""
    from numpyro.infer.util import log_likelihood

    full = dict(data, env_mask=np.ones_like(data["env_mask"]), y_mask=np.ones_like(data["y_mask"]))
    ll = log_likelihood(model, {k: v for k, v in samples.items() if not k.startswith("obs")}, full)
    x = np.asarray(ll["obs_E" if which == "E" else "obs_Y"]).sum(1)  # [S, M], summed over epochs or years
    return logmeanexp(x, 0)


def block_boot(diff, blocks, B=1000, seed=0):
    u, inv = np.unique(blocks, return_inverse=True)
    per = np.bincount(inv, weights=diff)
    rng = np.random.default_rng(seed)
    boot = np.array([per[rng.integers(0, len(u), len(u))].sum() for _ in range(B)])
    return float(diff.sum()), float(np.quantile(boot, 0.05)), float(np.quantile(boot, 0.95))


def cross_validate(data, models, prior="default", warmup=500, samples=500):
    f = folds(data["block"])
    out = {"E": {m: np.full(len(f), np.nan) for m in models}, "Y": {m: np.full(len(f), np.nan) for m in models},
           "diag": []}
    for which in ("E", "Y"):
        for k in range(FOLDS):
            d = dict(data)
            hide = f == k
            if which == "E":
                d["env_mask"] = data["env_mask"] & ~hide[None, :]
            else:
                d["y_mask"] = data["y_mask"] & ~hide[None, :]
            for m in models:
                s, diag = lt.fit(partial(MODELS[m], prior=prior), d, seed=k, warmup=warmup, samples=samples)
                out[which][m][hide] = heldout_lpd(partial(MODELS[m], prior=prior), s, d, which)[hide]
                out["diag"].append({"which": which, "fold": k, "model": m, **diag})
                print(which, k, m, {kk: round(v, 3) for kk, v in diag.items()}, flush=True)
    return out


def gains(cv, blocks, pairs):
    res = {}
    for which in ("E", "Y"):
        for a, b in pairs:
            if a in cv[which] and b in cv[which]:
                diff = cv[which][a] - cv[which][b]
                ok = ~np.isnan(diff)
                tot, lo, hi = block_boot(diff[ok], blocks[ok])
                res[f"{which}: {a} - {b}"] = {"sum": tot, "lo90": lo, "hi90": hi, "n_meshes": int(ok.sum())}
    return res


def ppc(model, samples, data, seed=0):
    import jax
    from numpyro.infer import Predictive

    d = dict(data, E=None, Y=None)
    pred = Predictive(model, {k: v for k, v in samples.items() if not k.startswith("obs")})(jax.random.PRNGKey(seed), d)
    Y, E = np.asarray(pred["obs_Y"]), np.asarray(pred["obs_E"])
    obs = {"year_total": data["Y"].sum(1), "zero_share": (data["Y"] == 0).mean(1),
           "mesh_total_var": np.var(data["Y"].sum(0)), "E_rate": data["E"].mean(1)}
    rep = {"year_total": Y.sum(2), "zero_share": (Y == 0).mean(2), "mesh_total_var": np.var(Y.sum(1), axis=1),
           "E_rate": E.mean(2)}
    out = {}
    for k in obs:
        o = np.atleast_1d(np.asarray(obs[k], float))
        r = np.asarray(rep[k], float).reshape(len(rep[k]), -1)
        out[k] = {"observed": o.tolist(), "p_rep_ge_obs": (r >= o[None, :]).mean(0).tolist(),
                  "rep_median": np.median(r, 0).tolist()}
    return out


def summarise(s, keys):
    return {k: {"mean": float(np.mean(s[k])), "lo90": lt.interval(s[k])[0], "hi90": lt.interval(s[k])[1]}
            for k in keys if k in s and np.ndim(s[k]) == 1}


def main():
    import numpyro

    numpyro.set_host_device_count(4)
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("mode", choices=["full", "cv", "f1"])
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("out", type=Path)
    a.add_argument("--prior", default="default", choices=list(lt.PRIORS))
    a.add_argument("--models", nargs="+", default=["L0", "L0H", "L1", "L2", "L2x"])
    a.add_argument("--all-meshes", action="store_true", help="sensitivity: every intersecting mesh in the yo4 frame")
    args = a.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists")
    t0 = time.time()
    meta = json.loads((args.art / "grid.json").read_text(encoding="utf-8"))
    data = sm.load_core(args.work / "mesh/mesh_table.parquet", meta, all_meshes=args.all_meshes)
    res = {"mode": args.mode, "prior": args.prior, "n_meshes": int(len(data["H"])), "all_meshes": args.all_meshes,
           "derived": "posterior summaries of latent model scores; not observations of bears or people"}
    if args.mode == "full":
        res["models"] = {}
        for m in args.models:
            model = partial(MODELS[m], prior=args.prior)
            s, diag = lt.fit(model, data, seed=0, chains=4, warmup=1000, samples=1000)
            ok = diag["max_rhat"] <= 1.01 and diag["min_ess"] >= 400 and diag["divergent_share"] <= 0.005
            row = {"diagnostics": diag, "converged_strict": ok,
                   "params": summarise(s, ["lam_E", "lam_K", "c_E", "c_K", "phi", "sr", "kappa", "s_E", "s_K"]),
                   "beta": np.mean(s["beta"], 0).tolist() if "beta" in s else None,
                   "ppc": ppc(model, s, data)}
            if "b" in s:
                row["corr_b_mean_with_H"] = float(np.corrcoef(s["b"].mean(0), data["H"])[0, 1])
                row["corr_b_mean_with_tree"] = float(np.corrcoef(s["b"].mean(0), data["z_tree"])[0, 1])
                np.savez_compressed(args.work / f"fit/{args.out.stem}_{m}_b.npz", mesh_code=data["mesh_code"],
                                    b_mean=s["b"].mean(0), b_sd=s["b"].std(0), H=data["H"])
            res["models"][m] = row
            print(m, diag, ok, {k: round(v["mean"], 3) for k, v in row["params"].items()}, flush=True)
    elif args.mode == "cv":
        cv = cross_validate(data, args.models, prior=args.prior)
        res["gains"] = gains(cv, data["block"], [("L1", "L0"), ("L2", "L0H"), ("L2", "L1"), ("L2x", "L2"), ("L0H", "L0")])
        res["lpd_sum"] = {w: {m: float(np.nansum(v)) for m, v in cv[w].items()} for w in ("E", "Y")}
        res["diag"] = cv["diag"]
        res["converged_share"] = float(np.mean([d["max_rhat"] <= 1.05 and d["divergent_share"] <= 0.01 for d in cv["diag"]]))
        print(json.dumps(res["gains"], indent=1))
    else:
        res["shuffles"] = []
        for seed in range(10):
            d = dict(data)
            d["E"], d["env_mask"] = shuffle_env(data, seed)
            cv = cross_validate(d, ["L0", "L1"], prior=args.prior)
            g = gains(cv, data["block"], [("L1", "L0")])
            s, diag = lt.fit(partial(MODELS["L1"], prior=args.prior), d, seed=0, chains=4, warmup=1000, samples=1000)
            res["shuffles"].append({"seed": seed, "kept_records": int(d["env_mask"][0].sum()), "gains": g,
                                    "lam_E": summarise(s, ["lam_E"])["lam_E"], "full_diag": diag})
            print("shuffle", seed, json.dumps(g), res["shuffles"][-1]["lam_E"], flush=True)
    res["seconds"] = round(time.time() - t0)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
