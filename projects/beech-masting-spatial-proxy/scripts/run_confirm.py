"""B2 (decisive) and B3 (falsification, robustness, residuals) on the confirmation years t = 2000-2008, once, with
the specification frozen in outputs/b1_frozen_choice.json (EXPERIMENT_PLAN.md). Coefficients are refitted in each
fold; training may use every target year 1990-2008 allowed by the scheme.

Writes outputs/b2_confirm.json, outputs/b3_checks.json and the predictions to ART/confirm_predictions.parquet.
Stops if the choice file is missing or the outputs exist.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj --with pyarrow python \
      projects/beech-masting-spatial-proxy/scripts/run_confirm.py projects/beech-masting-spatial-proxy/outputs \
      artifacts/beech-masting-spatial-proxy
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import model as M
import rows as R

CONF = list(range(2000, 2009))
ALL = list(range(1990, 2009))
MODELS = ["M0", "M1", "M2", "M3", "M4", "M5", "M7"]
PERMS = 200


def evaluate(pred, models):
    err = M.common_rows(M.row_errors(pred), models)
    return err, M.scores(err)


def g_test(pred, err, g):
    boot = M.year_bootstrap(err, g, "M1")
    reps = M.repeat_diffs(pred[pred.model.isin([g, "M1"])], g, "M1")
    neg = int(sum(d < 0 for d in reps))
    ok = boot["hi90"] < 0 and neg >= 9
    return {**boot, "repeat_diffs": reps, "repeats_negative": neg, "passes": bool(ok)}


def morans_i(res, sites, k=M.K_NEAR):
    """Moran's I of the residuals within one year, k nearest sites, rows summing to 1."""
    xy = sites.set_index("ID").loc[res.ID, ["x", "y_m"]].to_numpy()
    z = res.r.to_numpy() - res.r.mean()
    n = len(z)
    d = np.hypot(xy[:, 0, None] - xy[None, :, 0], xy[:, 1, None] - xy[None, :, 1])
    np.fill_diagonal(d, np.inf)
    W = np.zeros((n, n))
    for i in range(n):
        W[i, np.argsort(d[i])[:k]] = 1.0 / k
    return float(n / W.sum() * (z @ W @ z) / (z @ z))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    a = ap.parse_args()
    choice_path = a.outputs / "b1_frozen_choice.json"
    if not choice_path.exists():
        raise SystemExit("B1 has not been frozen")
    for p in (a.outputs / "b2_confirm.json", a.outputs / "b3_checks.json"):
        if p.exists():
            raise SystemExit(f"{p} exists: the confirmation has been run")
    body = choice_path.read_text(encoding="utf-8")
    choice = json.loads(body)
    r, w, g = choice["radius"], choice["water"], choice["g_star"]
    ranks, climate, terrain, sites = R.load(a.outputs)
    rows = R.build(ranks, climate, terrain, sites, r)

    pred = {"A": M.run_A(rows, CONF, ALL, MODELS, w)}
    caches = {"B": {}, "C": {}}
    pred["B"] = M.run_BC(rows, ranks, sites, "B", CONF, ALL, MODELS + ["M1y"], w, lag_cache=caches["B"])
    pred["C"] = M.run_BC(rows, ranks, sites, "C", CONF, ALL, MODELS, w, lag_cache=caches["C"])
    a.art.mkdir(parents=True, exist_ok=True)
    pd.concat([p.assign(scheme=s) for s, p in pred.items()]).to_parquet(a.art / "confirm_predictions.parquet",
                                                                        index=False)
    err, sc = {}, {}
    for s, p in pred.items():
        ms = MODELS + (["M1y"] if s == "B" else [])
        err[s], sc[s] = evaluate(p, ms)
    claims = {
        "C1": {"scheme": "A", **M.year_bootstrap(err["A"], "M2", "M1")},
        "C2": {"scheme": "B", **M.year_bootstrap(err["B"], "M3", "M2")},
        "C3": {"scheme": "C", **M.year_bootstrap(err["C"], "M5", "M4")},
    }
    for c in claims.values():
        c["verdict"] = M.rule(c)
    gate = {"g_star": g, "B": g_test(pred["B"], err["B"], g), "C": g_test(pred["C"], err["C"], g)}
    gate["verdict"] = "supported" if gate["B"]["passes"] and gate["C"]["passes"] else "not supported"
    aux = {s: {m: M.year_bootstrap(err[s], m, "M1") for m in sc[s] if m != "M1"} for s in sc}
    aux["C3_in_B"] = M.year_bootstrap(err["B"], "M5", "M4")
    per_year = {s: err[s].assign(se=err[s].se).groupby(["model", "t"]).se.mean().pow(0.5).unstack().round(4)
                .to_dict(orient="index") for s in err}
    out = {"choice": choice, "choice_sha256": hashlib.sha256(body.encode()).hexdigest(),
           "confirm_targets": [CONF[0], CONF[-1]], "scores": sc, "claims": claims, "gate": gate,
           "aux_vs_M1": aux, "rmse_by_year": per_year,
           "rows_by_scheme": {s: int(len(err[s]) / err[s].model.nunique()) for s in err}}
    (a.outputs / "b2_confirm.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"scores": {s: {m: round(v["rmse"], 4) for m, v in sc[s].items()} for s in sc},
                      "claims": {k: (round(v["diff"], 4), round(v["lo90"], 4), round(v["hi90"], 4), v["verdict"])
                                 for k, v in claims.items()},
                      "gate": {s: (round(gate[s]["diff"], 4), round(gate[s]["hi90"], 4), gate[s]["repeats_negative"])
                               for s in ("B", "C")}, "gate_verdict": gate["verdict"]}, indent=1), flush=True)

    # ---- B3: falsification ----
    rng = np.random.default_rng(0)
    clim = R.climate_by_t(climate).set_index(["ID", "t"])[R.CLIMATE_COLS]
    actual_C = sc["C"][g]["rmse"]
    actual_B = sc["B"][g]["rmse"]
    keys_C = err["C"][err["C"].model == g][["ID", "t"]]
    keys_B = err["B"][err["B"].model == g][["ID", "t"]]

    def rmse_on(p, keys):
        e = M.row_errors(p).merge(keys, on=["ID", "t"])
        return float(np.sqrt(e.se.mean()))

    f1 = []
    for i in range(PERMS):
        perm = dict(zip(ALL, rng.permutation(ALL)))

        def tf(sub, perm=perm):
            sub = sub.copy()
            src = pd.MultiIndex.from_arrays([sub.ID.to_numpy(), sub.t.map(perm).to_numpy()])
            sub[R.CLIMATE_COLS] = clim.loc[src].to_numpy()
            return sub

        f1.append(rmse_on(M.run_BC(rows, ranks, sites, "C", CONF, ALL, [g], w, transform=tf,
                                   lag_cache=caches["C"]), keys_C))
        if i % 20 == 0:
            print("F1", i, round(f1[-1], 4), flush=True)
    ter_cols = ["elev", "slope", "northness", "eastness", "relief", "tpi"]
    ter = rows.groupby("ID")[ter_cols].first()
    f2 = []
    for i in range(PERMS):
        ids = ter.index.to_numpy()
        mapping = dict(zip(ids, rng.permutation(ids)))

        def tf2(sub, mapping=mapping):
            sub = sub.copy()
            sub[ter_cols] = ter.loc[sub.ID.map(mapping)].to_numpy()
            return sub

        f2.append(rmse_on(M.run_BC(rows, ranks, sites, "B", CONF, ALL, [g], w, transform=tf2,
                                   lag_cache=caches["B"]), keys_B))
        if i % 20 == 0:
            print("F2", i, round(f2[-1], 4), flush=True)
    checks = {
        "F1_climate_years_C": {"actual": actual_C, "perm_p05": float(np.percentile(f1, 5)),
                               "perm_median": float(np.median(f1)), "share_perm_better": float(np.mean(np.array(f1) <= actual_C)),
                               "passes": bool(actual_C < np.percentile(f1, 5)), "perms": PERMS},
        "F2_terrain_sites_B": {"actual": actual_B, "perm_p05": float(np.percentile(f2, 5)),
                               "perm_median": float(np.median(f2)), "share_perm_better": float(np.mean(np.array(f2) <= actual_B)),
                               "passes": bool(actual_B < np.percentile(f2, 5)), "perms": PERMS},
    }
    # ---- robustness (not used for decisions) ----
    rob = {}
    for name, kw in {"buffer_0km": {"buffer_m": 0.0}, "block_30km": {"block_m": 30_000.0},
                     "k3": {"k": 3}, "k10": {"k": 10}}.items():
        rob[name] = {}
        for s in ("B", "C"):
            p = M.run_BC(rows, ranks, sites, s, CONF, ALL, ["M1", g], w, **kw)
            e, scs = evaluate(p, ["M1", g])
            rob[name][s] = {"rmse": {m: v["rmse"] for m, v in scs.items()}, **M.year_bootstrap(e, g, "M1")}
    checks["robustness"] = rob
    # ---- residuals ----
    e = err["C"][err["C"].model == g].assign(r=lambda d: d.pred - d.y)
    mi = {int(t): morans_i(gr, sites) for t, gr in e.groupby("t")}
    checks["residual_morans_i_C"] = {"by_year": mi, "mean": float(np.mean(list(mi.values()))),
                                     "min": float(min(mi.values())), "max": float(max(mi.values()))}
    (a.outputs / "b3_checks.json").write_text(json.dumps(checks, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in checks.items() if k != "robustness"}, indent=1))


if __name__ == "__main__":
    main()
