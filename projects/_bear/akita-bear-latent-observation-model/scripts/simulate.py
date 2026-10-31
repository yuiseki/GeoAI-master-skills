"""Synthetic data on the real 5 km core meshes (EXPERIMENT_PLAN.md): the same covariates, municipalities, offsets,
observation epochs and missingness (two Ministry epochs, four Kumadas years, no overlap in time), with a known
latent truth. Synthetic records are not observations and are never written next to real data.

Scenarios S1 bear expansion only, S2 reporting change only, S3 human-side change only, S4 bear + reporting, S5 none.
Value-of-information extras (V1-V6) add a synthetic data stream generated from the same truth.
"""

import numpy as np

import latent as lt

SCENARIOS = ("S1", "S2", "S3", "S4", "S5")
TRUE = {"lam_E": 1.0, "lam_K": 0.8, "c_E": 0.5, "c_K": 1.0, "phi": 2.0, "sd_r": 0.3, "sd_beta": 0.5}
BEAR_MEAN, BEAR_TREE, BEAR_NOISE = 0.4, 0.4, 0.2
REP_GLOBAL, REP_CITY = 0.4, 0.6
HUMAN_UP = 0.6
FRAC = np.array([0.0, 1 / 3, 2 / 3, 1.0])  # 2023 .. 2026


def load_core(mesh_table, grid_meta):
    """Data dict of the real core meshes (records and counts included)."""
    import pandas as pd

    t = pd.read_parquet(mesh_table)
    t = t[t.core].reset_index(drop=True)
    codes = grid_meta["codes"]
    used = sorted(t.muni.unique())
    gidx = {m: i for i, m in enumerate(used)}
    XB = t[[c for c in t.columns if c.startswith("zB_")]].to_numpy(float)
    return {"XB": XB, "H": t.H.to_numpy(float), "muni": t.muni.map(gidx).to_numpy(), "G": len(used),
            "offset": np.log(t.n_cells.to_numpy(float)), "E": t[["E6", "E7"]].to_numpy(int).T,
            "Y": t[[f"Y{y}" for y in lt.YEARS]].to_numpy(int).T, "env_mask": np.ones((2, len(t)), bool),
            "y_mask": np.ones((4, len(t)), bool), "z_tree": t.zB_tree.to_numpy(float),
            "city": int(gidx[codes.index("05201")]), "block": t.mesh_code.str[:6].to_numpy(),
            "mesh_code": t.mesh_code.to_numpy()}


def _logistic(x):
    return 1 / (1 + np.exp(-x))


def _solve_intercept(lin, target):
    """a with mean(logistic(a + lin)) = target (bisection)."""
    lo, hi = -20.0, 20.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _logistic(mid + lin).mean() < target else (lo, mid)
    return (lo + hi) / 2


def truth(data, scenario, seed, targets):
    """The latent truth and its estimands. targets: E6 and E7 record rates, base mean count per mesh."""
    if scenario not in SCENARIOS:
        raise ValueError(scenario)
    rng = np.random.default_rng(seed)
    M, G = data["XB"].shape[0], data["G"]
    beta = rng.normal(0, TRUE["sd_beta"], data["XB"].shape[1])
    b = data["XB"] @ beta + rng.normal(0, 1, M)
    r0 = rng.normal(0, TRUE["sd_r"], G)
    d = np.zeros((4, M))
    rep = np.tile(r0, (4, 1))
    dH = np.zeros((4, M))
    if scenario in ("S1", "S4"):
        e = BEAR_TREE * (-(data["z_tree"] - data["z_tree"].mean()) / data["z_tree"].std()) + rng.normal(0, BEAR_NOISE, M)
        d = FRAC[:, None] * (BEAR_MEAN + e)[None, :]
    if scenario in ("S2", "S4"):
        rep = rep + REP_GLOBAL * FRAC[:, None]
        rep[:, data["city"]] += REP_CITY * FRAC
    if scenario == "S3":
        top = data["H"] >= np.quantile(data["H"], 0.75)
        dH = FRAC[:, None] * (HUMAN_UP * top)[None, :]
    aE = [_solve_intercept(TRUE["lam_E"] * b + TRUE["c_E"] * data["H"], targets[k]) for k in ("E6", "E7")]
    base = data["offset"] + TRUE["lam_K"] * b + TRUE["c_K"] * data["H"] + r0[data["muni"]]
    a0 = np.log(targets["count"] * M / np.exp(base).sum())
    z = data["z_tree"] - data["z_tree"].mean()
    T_R = (rep[3] - rep[0])[data["muni"]].mean()
    return {"b": b, "beta": beta, "d": d, "rep": rep, "dH": dH, "aE": np.array(aE), "a0": a0,
            "T_B": float(d[3].mean()), "T_R": float(T_R),
            "S_B": float(((d[3] - d[3].mean()) * z).sum() / (z ** 2).sum()), "scenario": scenario, "seed": seed}


def simulate(data, tr, seed, extras=()):
    """Synthetic records from the truth, in a data dict shaped like the real one (plus extras)."""
    rng = np.random.default_rng(10_000 + seed)
    M = data["XB"].shape[0]
    out = {k: data[k] for k in ("XB", "H", "muni", "G", "offset", "env_mask", "y_mask", "z_tree", "city", "block")}
    linE = tr["aE"][:, None] + TRUE["lam_E"] * tr["b"][None, :] + TRUE["c_E"] * data["H"][None, :]
    out["E"] = (rng.random((2, M)) < _logistic(linE)).astype(int)
    By = tr["b"][None, :] + tr["d"]
    Hy = data["H"][None, :] + tr["dH"]
    mu = np.exp(data["offset"][None, :] + tr["a0"] + tr["rep"][:, data["muni"]] + TRUE["lam_K"] * By + TRUE["c_K"] * Hy)
    p = TRUE["phi"] / (TRUE["phi"] + mu)
    out["Y"] = rng.negative_binomial(TRUE["phi"], p)
    ex = {}
    for v in extras:
        ex.update(extra(v, data, tr, By, Hy, rng))
    return out, ex


def extra(name, data, tr, By, Hy, rng):
    M, G = data["XB"].shape[0], data["G"]
    if name == "V1":  # 50 fixed sites x 4 years, constant effort
        sites = rng.choice(M, 50, replace=False)
        mesh = np.tile(sites, 4)
        year = np.repeat(np.arange(4), 50)
        effort = np.ones(200)
        return {"camera": _camera(mesh, year, effort, By, rng)}
    if name == "V2":  # 50 new sites each year, recorded effort 0.5-2
        mesh = np.concatenate([rng.choice(M, 50, replace=False) for _ in range(4)])
        year = np.repeat(np.arange(4), 50)
        effort = np.exp(rng.uniform(np.log(0.5), np.log(2), 200))
        return {"camera": _camera(mesh, year, effort, By, rng)}
    if name == "V3":  # captures per municipality x year with recorded effort
        W = np.zeros((G, M))
        W[data["muni"], np.arange(M)] = 1
        W = W / W.sum(1, keepdims=True)
        effort = np.exp(rng.uniform(np.log(0.5), np.log(2), (4, G)))
        mB = By @ W.T
        a_cap = np.log(10.0) - np.log(np.exp(mB[0]).mean())
        return {"capture": {"W": W, "effort": effort, "count": rng.poisson(effort * np.exp(a_cap + mB))}}
    if name == "V4":  # Ministry-style survey in 2023 and 2026, same method as E7
        lin = tr["aE"][1] + TRUE["lam_E"] * By[[0, 3]] + TRUE["c_E"] * data["H"][None, :]
        return {"env2020s": {"E8": (rng.random((2, M)) < _logistic(lin)).astype(int)}}
    if name == "V5":  # recorded operational history: a global change from 2024, Akita City from 2025
        Z = np.zeros((2, 4, G))
        Z[0, 1:, :] = 1
        Z[1, 2:, data["city"]] = 1
        return {"history": {"Z": Z}}
    if name == "V6":  # time-varying human activity observed with error
        return {"H_obs": Hy + rng.normal(0, 0.1, Hy.shape)}
    raise ValueError(name)


def _camera(mesh, year, effort, By, rng):
    a_cam = np.log(5.0) - np.log(np.exp(By[0]).mean())
    days = rng.poisson(effort * np.exp(a_cam + By[year, mesh]))
    return {"mesh": mesh, "year": year, "effort": effort, "days": days}


def history_truth(data, tr):
    """For V5 the reporting change must follow the recorded history: S2's change as indicator steps."""
    rep = np.tile(tr["rep"][0], (4, 1))
    if not np.allclose(tr["rep"], rep):
        rep = rep + REP_GLOBAL * np.array([0, 1, 1, 1])[:, None]
        rep[:, data["city"]] += REP_CITY * np.array([0, 0, 1, 1])
    t = dict(tr)
    t["rep"] = rep
    t["T_R"] = float((rep[3] - rep[0])[data["muni"]].mean())
    return t
