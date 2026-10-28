"""Audit whether the 100 recorded event counts can rank occurrence.

Input: data/units.csv (one row per 1 km cell).
Outputs: outputs/*.json, *.csv, *.png, evidence.txt.

Run with the project venv:
    /tmp/venv-geoai/bin/python scripts/analysis.py
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from matplotlib.colors import Normalize, TwoSlopeNorm
from scipy import stats
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OUT = ROOT / "outputs"
DATA = ROOT / "data" / "units.csv"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO / ".agents" / "skills" / "analysis-visualize" / "scripts"))
from cjk_font import use_cjk_font  # noqa: E402

FONT = use_cjk_font(
    "観測記録 調査回数 人口あたり 記録/回 残差 北 南 西 東 行 列 区画 候補 探索 "
    "記録された出来事の数 調査員が訪れた回数 人口 1,000 人あたり 1 km 四方 "
    "多い 少ない 高い 低い 度 回 人 件 標準化残差 北東 3×5 ブロック 20 回 4 回 "
    "西 20 回 東 4 回 記録の分布 努力の分布 人口の分布 率の分布 差 比 行番号 "
)

df = pd.read_csv(DATA)
df["region"] = np.where(df["col"] < 5, "west", "east")
df["north3"] = (df["row"] <= 2).astype(int)
df["east_north"] = ((df["region"] == "east") & (df["north3"] == 1)).astype(int)
df["rate_pop1000"] = df["observed"] / df["population"] * 1000.0
df["rate_visit"] = df["observed"] / df["survey_visits"]

# ---------------------------------------------------------------- sanity
checks = {
    "n_rows": int(len(df)),
    "n_cols": int(df.shape[1]),
    "missing": {c: int(df[c].isna().sum()) for c in df.columns},
    "n_zero_observed": int((df["observed"] == 0).sum()),
    "area_values": sorted(df["area_km2"].unique().tolist()),
    "row_population_unique": {int(r): sorted(g["population"].unique().tolist()) for r, g in df.groupby("row")},
    "col_visits_unique": {int(c): sorted(g["survey_visits"].unique().tolist()) for c, g in df.groupby("col")},
    "population_west_east": {
        "west": int(df.loc[df.region == "west", "population"].sum()),
        "east": int(df.loc[df.region == "east", "population"].sum()),
    },
}
assert len(df) == 100
assert all(v == 0 for v in checks["missing"].values())
assert checks["area_values"] == [1.0]
assert all(len(v) == 1 for v in checks["row_population_unique"].values())
assert all(len(v) == 1 for v in checks["col_visits_unique"].values())
assert checks["population_west_east"]["west"] == checks["population_west_east"]["east"]

# ---------------------------------------------------------------- group totals
GROUP_DEFS = {
    "all": np.ones(len(df), dtype=bool),
    "west": (df["region"] == "west").to_numpy(),
    "east": (df["region"] == "east").to_numpy(),
    "west_north": ((df["region"] == "west") & (df["north3"] == 1)).to_numpy(),
    "west_south": ((df["region"] == "west") & (df["north3"] == 0)).to_numpy(),
    "east_north": ((df["region"] == "east") & (df["north3"] == 1)).to_numpy(),
    "east_south": ((df["region"] == "east") & (df["north3"] == 0)).to_numpy(),
    "north3": (df["north3"] == 1).to_numpy(),
    "south7": (df["north3"] == 0).to_numpy(),
}
group_rows = []
for name, mask in GROUP_DEFS.items():
    g = df.loc[mask]
    pop = int(g["population"].sum())
    vis = int(g["survey_visits"].sum())
    obs = int(g["observed"].sum())
    group_rows.append(
        {
            "group": name,
            "cells": int(len(g)),
            "population": pop,
            "visits": vis,
            "observed": obs,
            "observed_per_1000_pop": obs / pop * 1000.0 if pop else np.nan,
            "observed_per_visit": obs / vis if vis else np.nan,
            "visits_per_1000_pop": vis / pop * 1000.0 if pop else np.nan,
            "mean_population_per_cell": pop / len(g) if len(g) else np.nan,
        }
    )
groups = pd.DataFrame(group_rows)
groups.to_csv(OUT / "group_rates.csv", index=False)


def gv(group: str, col: str) -> float:
    return float(groups.loc[groups["group"] == group, col].iloc[0])


def decompose(numerator: str, denominator: str) -> dict:
    """Record rate per person = visits per person x records per visit."""
    obs_ratio = gv(numerator, "observed_per_1000_pop") / gv(denominator, "observed_per_1000_pop")
    visit_ratio = gv(numerator, "visits_per_1000_pop") / gv(denominator, "visits_per_1000_pop")
    per_visit_ratio = gv(numerator, "observed_per_visit") / gv(denominator, "observed_per_visit")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "observed_per_1000": {
            "numerator": gv(numerator, "observed_per_1000_pop"),
            "denominator": gv(denominator, "observed_per_1000_pop"),
            "ratio": obs_ratio,
        },
        "visits_per_1000": {
            "numerator": gv(numerator, "visits_per_1000_pop"),
            "denominator": gv(denominator, "visits_per_1000_pop"),
            "ratio": visit_ratio,
        },
        "observed_per_visit": {
            "numerator": gv(numerator, "observed_per_visit"),
            "denominator": gv(denominator, "observed_per_visit"),
            "ratio": per_visit_ratio,
        },
        "product_of_ratios": visit_ratio * per_visit_ratio,
    }


decomposition = {
    "east_north_vs_south": decompose("east_north", "east_south"),
    "west_north_vs_south": decompose("west_north", "west_south"),
    "west_vs_east": decompose("west", "east"),
}


# exact Poisson rate-ratio CI via conditional binomial
def rate_ratio_ci(x1: int, e1: float, x2: int, e2: float, alpha: float = 0.05):
    """CI for (x1/e1)/(x2/e2), independent Poisson, conditional on x1+x2."""
    n = x1 + x2
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = x1 / n
    lo = stats.beta.ppf(alpha / 2, x1, n - x1 + 1) if x1 > 0 else 0.0
    hi = stats.beta.ppf(1 - alpha / 2, x1 + 1, n - x1) if x1 < n else 1.0
    scale = e2 / e1
    rr = (p / (1 - p)) * scale if 0 < p < 1 else np.nan
    rr_lo = (lo / (1 - lo)) * scale if lo < 1 else np.inf
    rr_hi = (hi / (1 - hi)) * scale if hi < 1 else np.inf
    return rr, rr_lo, rr_hi


# ---------------------------------------------------------------- row rates
row_rows = []
for r, g in df.groupby("row"):
    w = g[g.region == "west"]
    e = g[g.region == "east"]
    assert len(w) == 5 and len(e) == 5
    assert int(w["population"].iloc[0]) == int(e["population"].iloc[0])
    pop_cell = int(w["population"].iloc[0])
    pop_total = pop_cell * 5  # five cells per row in each region
    wo, eo = int(w["observed"].sum()), int(e["observed"].sum())
    wr, er = wo / pop_total * 1000.0, eo / pop_total * 1000.0
    # exact Poisson CI for each rate
    def pois_ci(x, exposure):
        lo = 0.0 if x == 0 else stats.chi2.ppf(0.025, 2 * x) / 2
        hi = stats.chi2.ppf(0.975, 2 * x + 2) / 2
        return lo / exposure, hi / exposure

    wlo, whi = pois_ci(wo, pop_total / 1000.0)
    elo, ehi = pois_ci(eo, pop_total / 1000.0)
    rr, rr_lo, rr_hi = rate_ratio_ci(wo, pop_total, eo, pop_total)
    ratio_se = np.sqrt(1 / wo + 1 / eo)
    row_rows.append(
        {
            "row": int(r),
            "population_per_cell": pop_cell,
            "population_total_row": pop_total,
            "west_observed": wo,
            "east_observed": eo,
            "west_rate_per_1000": wr,
            "west_rate_lo": wlo,
            "west_rate_hi": whi,
            "east_rate_per_1000": er,
            "east_rate_lo": elo,
            "east_rate_hi": ehi,
            "west_east_ratio": rr,
            "west_east_ratio_lo": rr_lo,
            "west_east_ratio_hi": rr_hi,
            "west_east_ratio_wald_lo": float(np.exp(np.log(wo / eo) - 1.96 * ratio_se)),
            "west_east_ratio_wald_hi": float(np.exp(np.log(wo / eo) + 1.96 * ratio_se)),
            "north3": int(r <= 2),
        }
    )
row_rates = pd.DataFrame(row_rows)
row_rates.to_csv(OUT / "row_rates.csv", index=False)

# ---------------------------------------------------------------- pooled ratios
obs_w = int(gv("west", "observed"))
obs_e = int(gv("east", "observed"))
pop_w = int(gv("west", "population"))
pop_e = int(gv("east", "population"))
vis_w = int(gv("west", "visits"))
vis_e = int(gv("east", "visits"))
rate_w = obs_w / pop_w * 1000.0
rate_e = obs_e / pop_e * 1000.0
rate_ratio_we = rate_w / rate_e
rate_ratio_we_ci = rate_ratio_ci(obs_w, pop_w, obs_e, pop_e)
visit_rate_w = obs_w / vis_w
visit_rate_e = obs_e / vis_e
visit_ratio_ew = visit_rate_e / visit_rate_w

# within-effort ratios
ne_obs, ne_pop = int(gv("east_north", "observed")), int(gv("east_north", "population"))
es_obs, es_pop = int(gv("east_south", "observed")), int(gv("east_south", "population"))
wn_obs, wn_pop = int(gv("west_north", "observed")), int(gv("west_north", "population"))
ws_obs, ws_pop = int(gv("west_south", "observed")), int(gv("west_south", "population"))
ne_rate = ne_obs / ne_pop * 1000.0
es_rate = es_obs / es_pop * 1000.0
wn_rate = wn_obs / wn_pop * 1000.0
ws_rate = ws_obs / ws_pop * 1000.0
ne_es_ratio, ne_es_lo, ne_es_hi = rate_ratio_ci(ne_obs, ne_pop, es_obs, es_pop)
wn_ws_ratio, wn_ws_lo, wn_ws_hi = rate_ratio_ci(wn_obs, wn_pop, ws_obs, ws_pop)
interaction = (ne_rate / es_rate) / (wn_rate / ws_rate)

# ---------------------------------------------------------------- poisson models
def fit_poisson(formula: str, data: pd.DataFrame):
    model = smf.glm(
        formula=formula,
        data=data,
        family=sm.families.Poisson(),
        offset=np.log(data["population"].astype(float)),
    )
    res = model.fit()
    disp = float(res.pearson_chi2 / res.df_resid)
    res_q = model.fit(scale="X2") if disp > 1.2 else None
    return res, res_q, disp


def coef_dict(res, term: str):
    beta = float(res.params[term])
    lo, hi = [float(v) for v in res.conf_int().loc[term]]
    return {
        "term": term,
        "coef": beta,
        "se": float(res.bse[term]),
        "rr": float(np.exp(beta)),
        "rr_lo": float(np.exp(lo)),
        "rr_hi": float(np.exp(hi)),
        "p": float(res.pvalues[term]),
    }


model_rows = []
models = {}
for name, formula, data in [
    ("M1_region", "observed ~ C(region, Treatment('west'))", df),
    ("M2_log_visits", "observed ~ np.log(survey_visits)", df),
    ("M3_east_north", "observed ~ north3", df[df.region == "east"].copy()),
    ("M4_west_north", "observed ~ north3", df[df.region == "west"].copy()),
    ("M5_2x2", "observed ~ C(region, Treatment('west')) * north3", df),
    ("M6_row_region", "observed ~ C(row) + C(region, Treatment('west'))", df),
    ("M6b_row_region_ne", "observed ~ C(row) + C(region, Treatment('west')) + east_north", df),
]:
    res, res_q, disp = fit_poisson(formula, data)
    models[name] = {"res": res, "res_q": res_q, "disp": disp, "formula": formula, "n": int(len(data))}
    terms = [t for t in res.params.index if t != "Intercept"]
    if name == "M1_region":
        target = "C(region, Treatment('west'))[T.east]"
    elif name == "M2_log_visits":
        target = "np.log(survey_visits)"
    elif name in ("M3_east_north", "M4_west_north"):
        target = "north3"
    elif name == "M5_2x2":
        target = "C(region, Treatment('west'))[T.east]:north3"
    elif name == "M6_row_region":
        target = "C(region, Treatment('west'))[T.east]"
    elif name == "M6b_row_region_ne":
        target = "east_north"
    else:
        target = terms[0]
    cd = coef_dict(res, target)
    cd.update(
        {
            "model": name,
            "n": int(len(data)),
            "df_resid": float(res.df_resid),
            "deviance": float(res.deviance),
            "pearson_chi2": float(res.pearson_chi2),
            "dispersion": disp,
            "aic": float(res.aic),
            "quasi_scale": float(res_q.scale) if res_q is not None else None,
            "quasi_se": float(res_q.bse[target]) if res_q is not None else None,
            "quasi_rr_lo": float(np.exp(res_q.conf_int().loc[target, 0])) if res_q is not None else None,
            "quasi_rr_hi": float(np.exp(res_q.conf_int().loc[target, 1])) if res_q is not None else None,
        }
    )
    model_rows.append(cd)
    print(name, cd)
model_table = pd.DataFrame(model_rows)
model_table.to_csv(OUT / "poisson_models.csv", index=False)

# LR test: row + region vs row + region + northeast
m6 = models["M6_row_region"]["res"]
m6b = models["M6b_row_region_ne"]["res"]
lr = 2 * (m6b.llf - m6.llf)
lr_df = m6b.df_model - m6.df_model
lr_p = float(stats.chi2.sf(lr, lr_df))
lr_test = {"lr": float(lr), "df": float(lr_df), "p": lr_p}

# negative binomial for the 2x2 model (sensitivity)
try:
    nb = smf.negativebinomial(
        "observed ~ C(region, Treatment('west')) * north3",
        data=df,
        offset=np.log(df["population"].astype(float)),
    ).fit(disp=0, maxiter=200)
    nb_term = "C(region, Treatment('west'))[T.east]:north3"
    nb_res = {
        "converged": bool(nb.mle_retvals.get("converged", True)),
        "coef": float(nb.params[nb_term]),
        "rr": float(np.exp(nb.params[nb_term])),
        "rr_lo": float(np.exp(nb.conf_int().loc[nb_term, 0])),
        "rr_hi": float(np.exp(nb.conf_int().loc[nb_term, 1])),
        "alpha": float(nb.params.get("alpha", np.nan)),
        "aic": float(nb.aic),
    }
except Exception as exc:  # pragma: no cover - diagnostic only
    nb_res = {"error": repr(exc)}

# ---------------------------------------------------------------- detection models
sat_ratio = rate_ratio_we
sat_target = lambda p: (1 - (1 - p) ** 20) / (1 - (1 - p) ** 4) - sat_ratio
p_sat = float(brentq(sat_target, 1e-8, 1 - 1e-8))
d20 = 1 - (1 - p_sat) ** 20
d4 = 1 - (1 - p_sat) ** 4
true_sat_w = rate_w / d20
true_sat_e = rate_e / d4
detection_rows = [
    {
        "model": "linear_in_visits",
        "assumption": "a visit records a constant fraction of events; no saturation",
        "true_rate_west_per_1000_per_visit": visit_rate_w,
        "true_rate_east_per_1000_per_visit": visit_rate_e,
        "west_east_ratio": visit_rate_w / visit_rate_e,
        "east_west_ratio": visit_rate_e / visit_rate_w,
        "detection_ratio_d4_over_d20": 4 / 20,
        "implied_west_east_ratio": (rate_w / rate_e) * (4 / 20),
    },
    {
        "model": "full_detection",
        "assumption": "both 20 and 4 visits record all events",
        "true_rate_west_per_1000": rate_w,
        "true_rate_east_per_1000": rate_e,
        "west_east_ratio": rate_ratio_we,
        "east_west_ratio": 1 / rate_ratio_we,
        "detection_ratio_d4_over_d20": 1.0,
        "implied_west_east_ratio": rate_ratio_we,
    },
    {
        "model": "saturating_common_p",
        "assumption": "each visit detects with probability p, independently; p common to all cells",
        "p_per_visit": p_sat,
        "detection_after_20": d20,
        "detection_after_4": d4,
        "detection_ratio_d4_over_d20": d4 / d20,
        "true_rate_west_per_1000": true_sat_w,
        "true_rate_east_per_1000": true_sat_e,
        "west_east_ratio": true_sat_w / true_sat_e,
        "east_west_ratio": true_sat_e / true_sat_w,
        "implied_west_east_ratio": rate_ratio_we * (d4 / d20),
    },
]
detection = pd.DataFrame(detection_rows)
detection.to_csv(OUT / "detection_models.csv", index=False)

# ---------------------------------------------------------------- row-level exact tests
rows_unique = sorted(df["row"].unique().tolist())


def pooled_rate(mask, col_region, rows_subset):
    m = mask & df["row"].isin(rows_subset) & (df["region"] == col_region)
    g = df.loc[m]
    return g["observed"].sum() / g["population"].sum() * 1000.0


def exact_row_permutation(stat_fn, observed_rows, alternative="greater"):
    vals = []
    for combo in itertools.combinations(rows_unique, 3):
        vals.append(stat_fn(set(combo)))
    obs = stat_fn(set(observed_rows))
    vals = np.asarray(vals)
    # Full enumeration includes the observed assignment, so do not add 1 to both
    # the count and the denominator (that is the Monte Carlo convention).
    if alternative == "greater":
        p = float(np.sum(vals >= obs - 1e-12) / len(vals))
    else:
        p = float(np.sum(vals <= obs + 1e-12) / len(vals))
    return {
        "observed": float(obs),
        "n_assignments": int(len(vals)),
        "p_one_sided": p,
        "min": float(vals.min()),
        "max": float(vals.max()),
        "mean": float(vals.mean()),
        "observed_rows": sorted(observed_rows),
    }


def east_rate_ratio(rows_subset):
    return pooled_rate(np.ones(len(df), dtype=bool), "east", rows_subset) / pooled_rate(
        np.ones(len(df), dtype=bool), "east", set(rows_unique) - set(rows_subset)
    )


def west_east_interaction(rows_subset):
    north = set(rows_subset)
    south = set(rows_unique) - north
    en = pooled_rate(np.ones(len(df), dtype=bool), "east", north)
    es = pooled_rate(np.ones(len(df), dtype=bool), "east", south)
    wn = pooled_rate(np.ones(len(df), dtype=bool), "west", north)
    ws = pooled_rate(np.ones(len(df), dtype=bool), "west", south)
    return (en / es) / (wn / ws)


def west_rate_ratio(rows_subset):
    return pooled_rate(np.ones(len(df), dtype=bool), "west", rows_subset) / pooled_rate(
        np.ones(len(df), dtype=bool), "west", set(rows_unique) - set(rows_subset)
    )


perm = {
    "east_north_vs_south": exact_row_permutation(east_rate_ratio, {0, 1, 2}, "greater"),
    "west_north_vs_south": exact_row_permutation(west_rate_ratio, {0, 1, 2}, "greater"),
    "interaction": exact_row_permutation(west_east_interaction, {0, 1, 2}, "greater"),
}

# rank positions (for reporting)
east_rates_by_row = row_rates.sort_values("east_rate_per_1000", ascending=False)["row"].tolist()
west_ratios_by_row = row_rates.sort_values("west_east_ratio", ascending=True)["row"].tolist()
rank_info = {
    "east_rate_rank_rows_high_to_low": [int(x) for x in east_rates_by_row],
    "east_north_rows_are_top3": bool(set(east_rates_by_row[:3]) == {0, 1, 2}),
    "west_east_ratio_rank_rows_low_to_high": [int(x) for x in west_ratios_by_row],
    "east_north_rows_are_bottom3_ratio": bool(set(west_ratios_by_row[:3]) == {0, 1, 2}),
}


def rate_for(d: pd.DataFrame, region: str, north: int) -> float:
    g = d[(d["region"] == region) & (d["north3"] == north)]
    return float(g["observed"].sum() / g["population"].sum())


def ne_es_for(d: pd.DataFrame) -> float:
    return rate_for(d, "east", 1) / rate_for(d, "east", 0)


def interaction_for(d: pd.DataFrame) -> float:
    return (rate_for(d, "east", 1) / rate_for(d, "east", 0)) / (
        rate_for(d, "west", 1) / rate_for(d, "west", 0)
    )


def row_bootstrap(stat_fn, n_boot: int = 10000, seed: int = 123):
    rng = np.random.default_rng(seed)
    rows = np.array(rows_unique)
    out = []
    for _ in range(n_boot):
        sampled = rng.choice(rows, size=len(rows), replace=True)
        parts = []
        for new_row, old_row in enumerate(sampled):
            g = df[df["row"] == old_row].copy()
            g["row_boot"] = new_row
            parts.append(g)
        bd = pd.concat(parts, ignore_index=True)
        if bd["north3"].nunique() < 2:
            continue
        out.append(stat_fn(bd))
    out = np.asarray(out)
    return {
        "n_boot": int(len(out)),
        "median": float(np.median(out)),
        "ci95_lo": float(np.quantile(out, 0.025)),
        "ci95_hi": float(np.quantile(out, 0.975)),
        "min": float(out.min()),
        "max": float(out.max()),
    }


bootstrap = {
    "ne_es_ratio": row_bootstrap(ne_es_for),
    "interaction": row_bootstrap(interaction_for),
}

# ---------------------------------------------------------------- leave-one-out
loo_rows = []
for drop_row in rows_unique:
    sub = df[df["row"] != drop_row]
    east = sub[sub.region == "east"]
    north = east[east.north3 == 1]
    south = east[east.north3 == 0]
    if len(north) and len(south):
        rr, lo, hi = rate_ratio_ci(
            int(north.observed.sum()), int(north.population.sum()), int(south.observed.sum()), int(south.population.sum())
        )
        wn = sub[(sub.region == "west") & (sub.north3 == 1)]
        ws = sub[(sub.region == "west") & (sub.north3 == 0)]
        inter = np.nan
        if len(wn) and len(ws):
            inter = (north.observed.sum() / north.population.sum()) / (south.observed.sum() / south.population.sum())
            inter /= (wn.observed.sum() / wn.population.sum()) / (ws.observed.sum() / ws.population.sum())
        loo_rows.append(
            {
                "variant": f"drop_row_{drop_row}",
                "kind": "row",
                "ne_es_ratio": rr,
                "ne_es_lo": lo,
                "ne_es_hi": hi,
                "interaction": float(inter),
            }
        )
for drop_id in df["unit_id"]:
    sub = df[df["unit_id"] != drop_id]
    east = sub[sub.region == "east"]
    north = east[east.north3 == 1]
    south = east[east.north3 == 0]
    if len(north) and len(south):
        rr, lo, hi = rate_ratio_ci(
            int(north.observed.sum()), int(north.population.sum()), int(south.observed.sum()), int(south.population.sum())
        )
        wn = sub[(sub.region == "west") & (sub.north3 == 1)]
        ws = sub[(sub.region == "west") & (sub.north3 == 0)]
        inter = (north.observed.sum() / north.population.sum()) / (south.observed.sum() / south.population.sum())
        inter /= (wn.observed.sum() / wn.population.sum()) / (ws.observed.sum() / ws.population.sum())
        loo_rows.append(
            {
                "variant": f"drop_{drop_id}",
                "kind": "cell",
                "ne_es_ratio": rr,
                "ne_es_lo": lo,
                "ne_es_hi": hi,
                "interaction": float(inter),
            }
        )
loo = pd.DataFrame(loo_rows)
loo.to_csv(OUT / "leave_one_out.csv", index=False)

# area-denominator sensitivity (area is constant, so this is raw counts)
area_rates = {
    "west_per_km2": obs_w / float(df.loc[df.region == "west", "area_km2"].sum()),
    "east_per_km2": obs_e / float(df.loc[df.region == "east", "area_km2"].sum()),
    "northeast_per_km2": ne_obs / float(df.loc[df.east_north == 1, "area_km2"].sum()),
    "east_south_per_km2": es_obs / float(df.loc[(df.region == "east") & (df.north3 == 0), "area_km2"].sum()),
}
area_rates["west_east_ratio"] = area_rates["west_per_km2"] / area_rates["east_per_km2"]
area_rates["ne_es_ratio"] = area_rates["northeast_per_km2"] / area_rates["east_south_per_km2"]

# two-row bin sensitivity (east only): is the north-south contrast a knife-edge at row 2?
pair_rows = []
for start in range(0, 10, 2):
    sub = df[(df.region == "east") & (df["row"] >= start) & (df["row"] <= start + 1)]
    pop = int(sub["population"].sum())
    obs = int(sub["observed"].sum())
    pair_rows.append(
        {
            "rows": f"{start}-{start + 1}",
            "observed": obs,
            "population": pop,
            "rate_per_1000": obs / pop * 1000.0,
        }
    )
two_row_bins = pd.DataFrame(pair_rows)
two_row_bins["ratio_vs_last"] = two_row_bins["rate_per_1000"] / two_row_bins["rate_per_1000"].iloc[-1]
two_row_bins.to_csv(OUT / "two_row_bins.csv", index=False)

# ---------------------------------------------------------------- Moran's I on the grid
grid = {(int(r), int(c)): i for i, (r, c) in enumerate(zip(df["row"], df["col"]))}


def build_weights(kind: str = "queen") -> np.ndarray:
    n = len(df)
    w = np.zeros((n, n), dtype=float)
    for i, (r1, c1) in enumerate(zip(df["row"], df["col"])):
        for j, (r2, c2) in enumerate(zip(df["row"], df["col"])):
            if i == j:
                continue
            dr, dc = abs(int(r1) - int(r2)), abs(int(c1) - int(c2))
            if kind == "rook" and dr + dc == 1:
                w[i, j] = 1.0
            elif kind == "queen" and max(dr, dc) == 1:
                w[i, j] = 1.0
    rs = w.sum(axis=1, keepdims=True)
    rs[rs == 0] = 1.0
    return w / rs


def moran(values: np.ndarray, w: np.ndarray, n_perm: int = 9999, seed: int = 0):
    x = np.asarray(values, dtype=float)
    z = x - x.mean()
    denom = float(z @ z)
    if denom == 0:
        return {"I": np.nan, "p_positive": np.nan, "mean_perm": np.nan, "sd_perm": np.nan}
    i_obs = float((z @ w @ z) / denom)
    rng = np.random.default_rng(seed)
    perm_vals = np.empty(n_perm)
    for k in range(n_perm):
        zp = rng.permutation(z)
        perm_vals[k] = float((zp @ w @ zp) / denom)
    p_pos = float((1 + np.sum(perm_vals >= i_obs)) / (1 + n_perm))
    return {
        "I": i_obs,
        "p_positive": p_pos,
        "mean_perm": float(perm_vals.mean()),
        "sd_perm": float(perm_vals.std(ddof=1)),
    }


w_rook = build_weights("rook")
w_queen = build_weights("queen")
res_m6 = models["M6_row_region"]["res"]
pearson = pd.Series(res_m6.resid_pearson, index=df.index)
moran_vars = {
    "observed": df["observed"].to_numpy(float),
    "survey_visits": df["survey_visits"].to_numpy(float),
    "rate_per_1000_pop": df["rate_pop1000"].to_numpy(float),
    "rate_per_visit": df["rate_visit"].to_numpy(float),
    "pearson_residual_M6": pearson.to_numpy(float),
}
moran_out = {}
for vname, vals in moran_vars.items():
    moran_out[vname] = {
        "rook_k4": moran(vals, w_rook),
        "queen_k8": moran(vals, w_queen),
    }

# ---------------------------------------------------------------- figures
def pivot(values: pd.Series | np.ndarray) -> np.ndarray:
    s = pd.Series(np.asarray(values), index=df.index)
    s.index = pd.MultiIndex.from_arrays([df["row"], df["col"]])
    return s.unstack().sort_index().to_numpy()


def annotate_grid(ax, arr, fmt="{:.0f}", fontsize=7, cmap="Blues"):
    vmin, vmax = np.nanmin(arr), np.nanmax(arr)
    if vmin == vmax:
        vmax = vmin + 1
    im = ax.imshow(arr, origin="upper", cmap=cmap, vmin=vmin, vmax=vmax, aspect="equal")
    for r in range(10):
        for c in range(10):
            val = arr[r, c]
            if np.isnan(val):
                continue
            # choose readable text color
            frac = (val - vmin) / (vmax - vmin) if vmax > vmin else 0.5
            color = "white" if frac > 0.55 else "black"
            ax.text(c, r, fmt.format(val), ha="center", va="center", fontsize=fontsize, color=color)
    ax.set_xticks(range(10))
    ax.set_yticks(range(10))
    ax.set_xticks(np.arange(-0.5, 10, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 10, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.6)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(axis="both", labelsize=7)
    ax.set_xlabel("列 (西 → 東)", fontsize=8)
    ax.set_ylabel("行 (北 → 南)", fontsize=8)
    return im


def add_ne_outline(ax):
    from matplotlib.patches import Rectangle

    ax.add_patch(
        Rectangle((4.5, -0.5), 5, 3, fill=False, edgecolor="#d62728", linewidth=2.0, linestyle="--")
    )
    ax.text(7.0, -0.9, "北東 3×5 (候補)", ha="center", va="bottom", fontsize=8, color="#d62728")


def save_map(name, values, title, cbar_label, fmt="{:.0f}", cmap="Blues", outline=False, note=""):
    arr = pivot(values)
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    im = annotate_grid(ax, arr, fmt=fmt, cmap=cmap)
    ax.set_title(title, fontsize=11)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label(cbar_label, fontsize=8)
    cb.ax.tick_params(labelsize=7)
    if outline:
        add_ne_outline(ax)
    fig.text(0.02, 0.01, note, fontsize=7, color="#444444")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    meta = {
        "question": title,
        "source": "data/units.csv (2026-10-25, 100 cells)",
        "n": 100,
        "unit": cbar_label,
        "crs": "grid indices (row, col); 1 cell = 1 km²; no geographic CRS",
        "value_kind": "count" if "件" in cbar_label else "rate",
        "classification": "continuous, min-max for display; values printed in cells",
        "font": FONT,
        "note": note,
    }
    (OUT / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return path


map_paths = {}
map_paths["observed"] = save_map(
    "map_observed",
    df["observed"].to_numpy(float),
    "記録された出来事の数 (100 区画)",
    "記録 (件 / 区画)",
    fmt="{:.0f}",
    cmap="Blues",
    outline=True,
    note="行 0 = 北、列 0 = 西。赤破線は北東 3×5 区画 (探索の候補)。",
)
map_paths["visits"] = save_map(
    "map_visits",
    df["survey_visits"].to_numpy(float),
    "調査員が区画を訪れた回数",
    "調査回数 (回 / 区画)",
    fmt="{:.0f}",
    cmap="Purples",
    note="西 (列 0-4) は 20 回、東 (列 5-9) は 4 回。",
)
map_paths["rate_pop"] = save_map(
    "map_rate_pop",
    df["rate_pop1000"].to_numpy(float),
    "人口 1,000 人あたりの記録",
    "記録 (件 / 1,000 人)",
    fmt="{:.2f}",
    cmap="Blues",
    outline=True,
    note="人口を発生の機会とした率。赤破線は北東 3×5 区画 (探索の候補)。",
)
map_paths["rate_visit"] = save_map(
    "map_rate_visit",
    df["rate_visit"].to_numpy(float),
    "調査 1 回あたりの記録",
    "記録 (件 / 回)",
    fmt="{:.2f}",
    cmap="Greens",
    note="観測の努力をそろえた率。西は 20 回、東は 4 回の訪問。",
)

# residual map (diverging)
res_arr = pivot(pearson.to_numpy(float))
fig, ax = plt.subplots(figsize=(6.2, 5.6))
lim = float(np.nanmax(np.abs(res_arr)))
norm = TwoSlopeNorm(vmin=-lim, vcenter=0.0, vmax=lim)
im = ax.imshow(res_arr, origin="upper", cmap="RdBu_r", norm=norm, aspect="equal")
for r in range(10):
    for c in range(10):
        val = res_arr[r, c]
        color = "white" if abs(val) > lim * 0.6 else "black"
        ax.text(c, r, f"{val:.1f}", ha="center", va="center", fontsize=7, color=color)
ax.set_xticks(range(10))
ax.set_yticks(range(10))
ax.set_xticks(np.arange(-0.5, 10, 1), minor=True)
ax.set_yticks(np.arange(-0.5, 10, 1), minor=True)
ax.grid(which="minor", color="white", linewidth=0.6)
ax.tick_params(which="minor", length=0)
ax.tick_params(axis="both", labelsize=7)
ax.set_xlabel("列 (西 → 東)", fontsize=8)
ax.set_ylabel("行 (北 → 南)", fontsize=8)
ax.set_title("行 + 西東の主効果モデルの Pearson 残差", fontsize=11)
add_ne_outline(ax)
cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cb.set_label("Pearson 残差 (0 = 主効果モデルの期待)", fontsize=8)
cb.ax.tick_params(labelsize=7)
fig.text(
    0.02,
    0.01,
    "行ごとの率と西東の共通倍率を当てはめた後の残差。北東が正、東南が負なら、共通の努力効果だけでは説明できない。",
    fontsize=7,
    color="#444444",
)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(OUT / "map_residual_M6.png", dpi=160)
plt.close(fig)
(OUT / "map_residual_M6.json").write_text(
    json.dumps(
        {
            "question": "行 + 西東の主効果モデルの残差はどこに残るか",
            "source": "data/units.csv (2026-10-25); M6 Poisson GLM: observed ~ C(row) + C(region), offset log(population)",
            "n": 100,
            "unit": "Pearson residual",
            "crs": "grid indices (row, col); no geographic CRS",
            "classification": "diverging, symmetric around 0 at max abs residual",
            "font": FONT,
        },
        ensure_ascii=False,
        indent=2,
    )
)

# combined 2x2 map
fig, axes = plt.subplots(2, 2, figsize=(12.4, 10.8))
panels = [
    (df["observed"].to_numpy(float), "記録された出来事の数", "記録 (件 / 区画)", "{:.0f}", "Blues"),
    (df["survey_visits"].to_numpy(float), "調査員が訪れた回数", "調査回数 (回 / 区画)", "{:.0f}", "Purples"),
    (df["rate_pop1000"].to_numpy(float), "人口 1,000 人あたりの記録", "記録 (件 / 1,000 人)", "{:.2f}", "Blues"),
    (df["rate_visit"].to_numpy(float), "調査 1 回あたりの記録", "記録 (件 / 回)", "{:.2f}", "Greens"),
]
for ax, (vals, title, label, fmt, cmap) in zip(axes.ravel(), panels):
    arr = pivot(vals)
    im = annotate_grid(ax, arr, fmt=fmt, cmap=cmap)
    ax.set_title(title, fontsize=10)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label(label, fontsize=8)
    cb.ax.tick_params(labelsize=7)
    if "北東" in title or title in ("記録された出来事の数", "人口 1,000 人あたりの記録"):
        add_ne_outline(ax)
fig.suptitle("記録・努力・2 つの分母による率 (100 区画)", fontsize=13)
fig.text(
    0.02,
    0.01,
    "行 0 = 北、列 0 = 西。赤破線は北東 3×5 区画 (探索の候補)。値は各セルに表示。",
    fontsize=8,
    color="#444444",
)
fig.tight_layout(rect=(0, 0.03, 1, 0.96))
fig.savefig(OUT / "fig_maps_2x2.png", dpi=160)
plt.close(fig)

# row rate plot
fig, ax = plt.subplots(figsize=(8.4, 5.2))
for region, color, marker, label in [("west", "#1f77b4", "o", "西 (20 回)"), ("east", "#ff7f0e", "s", "東 (4 回)")]:
    sub = row_rates.copy()
    x = sub["population_per_cell"]
    y = sub[f"{region}_rate_per_1000"]
    lo = sub[f"{region}_rate_lo"]
    hi = sub[f"{region}_rate_hi"]
    ax.errorbar(x, y, yerr=[y - lo, hi - y], fmt=marker, color=color, label=label, capsize=2, markersize=5, linewidth=1)
    for _, r in sub.iterrows():
        ax.annotate(f"{int(r['row'])}", (r["population_per_cell"], r[f"{region}_rate_per_1000"]), fontsize=6, color=color, xytext=(3, 3), textcoords="offset points")
ax.axvspan(900, 2000, color="#999999", alpha=0.12)
ax.text(1450, ax.get_ylim()[1] * 0.96, "北 3 行\n(row 0-2)", ha="center", va="top", fontsize=8, color="#555555")
ax.set_xlabel("区画の人口 (人 / 1 km²)", fontsize=9)
ax.set_ylabel("人口 1,000 人あたりの記録 (件)", fontsize=9)
ax.set_title("行ごとの人口あたり記録率 (誤差棒はポアソンの 95% 区間)", fontsize=11)
ax.legend(fontsize=8, loc="center right")
ax.grid(alpha=0.25)
fig.text(0.02, 0.01, "データ: data/units.csv (2026-10-25)。西は行によらず約 4.3、東南は約 1.65、東北は約 2.6。", fontsize=7, color="#444444")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(OUT / "row_rate_plot.png", dpi=160)
plt.close(fig)
(OUT / "row_rate_plot.json").write_text(
    json.dumps(
        {
            "question": "行 (人口) ごとの人口あたり記録率は、努力の水準ごとにどう違うか",
            "source": "data/units.csv (2026-10-25); outputs/row_rates.csv",
            "n": 100,
            "unit": "records per 1,000 population",
            "interval": "Poisson exact 95% CI for each row total (5 cells)",
            "font": FONT,
        },
        ensure_ascii=False,
        indent=2,
    )
)

# row ratio plot
fig, ax = plt.subplots(figsize=(8.4, 4.6))
sub = row_rates.sort_values("row")
x = sub["row"].to_numpy()
y = sub["west_east_ratio"].to_numpy()
lo = sub["west_east_ratio_lo"].to_numpy()
hi = sub["west_east_ratio_hi"].to_numpy()
ax.errorbar(x, y, yerr=[y - lo, hi - y], fmt="o", color="#2ca02c", capsize=2, markersize=5, linewidth=1)
ax.axhline(rate_ratio_we, color="#444444", linestyle="--", linewidth=1, label=f"全体の比 {rate_ratio_we:.2f}")
ax.axvspan(-0.5, 2.5, color="#999999", alpha=0.12)
ax.text(1.0, ax.get_ylim()[1] * 0.96, "北 3 行 (row 0-2)", ha="center", va="top", fontsize=8, color="#555555")
ax.set_xlabel("行 (北 → 南)", fontsize=9)
ax.set_ylabel("西の記録 / 東の記録 (人口は同じなので約分)", fontsize=9)
ax.set_title("行ごとの西東の記録比 (誤差棒は条件付き二項の 95% 区間)", fontsize=11)
ax.set_xticks(range(10))
ax.legend(fontsize=8)
ax.grid(alpha=0.25)
fig.text(0.02, 0.01, "北 3 行は西東比が低い (東の記録が相対的に多い)。全体の比は 2.41。", fontsize=7, color="#444444")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(OUT / "row_ratio_plot.png", dpi=160)
plt.close(fig)
(OUT / "row_ratio_plot.json").write_text(
    json.dumps(
        {
            "question": "西東の記録比は行 (北/南) で変わるか",
            "source": "data/units.csv (2026-10-25); outputs/row_rates.csv",
            "n": 100,
            "unit": "west observed / east observed (same population within row)",
            "interval": "conditional binomial exact 95% CI for the ratio, independent Poisson",
            "font": FONT,
        },
        ensure_ascii=False,
        indent=2,
    )
)

# decomposition plot: records per person = visits per person x records per visit
fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.8))
labels = ["西\n北 3 行", "西\n南 7 行", "東\n北 3 行", "東\n南 7 行"]
keys = ["west_north", "west_south", "east_north", "east_south"]
colors = ["#9ecae1", "#1f77b4", "#ffbb78", "#ff7f0e"]
panels = [
    ("visits_per_1000_pop", "人口 1,000 人あたりの訪問回数", "訪問回数 / 1,000 人"),
    ("observed_per_visit", "訪問あたりの記録", "記録 / 訪問"),
    ("observed_per_1000_pop", "人口 1,000 人あたりの記録", "記録 / 1,000 人"),
]
for ax, (col, title, ylab) in zip(axes, panels):
    vals = [gv(k, col) for k in keys]
    ax.bar(range(len(keys)), vals, color=colors)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylab, fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.3f}", ha="center", va="bottom", fontsize=7)
fig.suptitle("人口あたり記録率の分解: 訪問の集中と訪問あたりの記録", fontsize=12)
fig.text(
    0.02,
    0.01,
    "西: 北/南 = 2.43 x 0.41 = 0.99。東: 北/南 = 2.43 x 0.65 = 1.59。"
    " 人口あたり記録率 = 人口あたり訪問回数 x 訪問あたり記録。",
    fontsize=8,
    color="#444444",
)
fig.tight_layout(rect=(0, 0.05, 1, 0.94))
fig.savefig(OUT / "fig_decomposition.png", dpi=160)
plt.close(fig)
(OUT / "fig_decomposition.json").write_text(
    json.dumps(
        {
            "question": "北東の人口あたり記録率の高さは、訪問の集中と訪問あたりの記録のどちらから来るか",
            "source": "data/units.csv (2026-10-25); outputs/group_rates.csv",
            "n": 100,
            "unit": "visits per 1,000 population; records per visit; records per 1,000 population",
            "note": "The third panel is the product of the first two; ratios are north 3 rows / south 7 rows within each region.",
            "font": FONT,
        },
        ensure_ascii=False,
        indent=2,
    )
)

# ---------------------------------------------------------------- summary json
def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


summary = {
    "data": "data/units.csv",
    "created": "2026-10-25",
    "checks": checks,
    "totals": {
        "observed": int(df.observed.sum()),
        "population": int(df.population.sum()),
        "visits": int(df.survey_visits.sum()),
    },
    "west_east": {
        "observed": {"west": obs_w, "east": obs_e, "ratio_west_east": obs_w / obs_e},
        "population": {"west": pop_w, "east": pop_e},
        "visits": {"west": vis_w, "east": vis_e, "ratio_west_east": vis_w / vis_e},
        "rate_per_1000_pop": {
            "west": rate_w,
            "east": rate_e,
            "ratio_west_east": rate_ratio_we,
            "ratio_ci95": rate_ratio_we_ci,
        },
        "rate_per_visit": {
            "west": visit_rate_w,
            "east": visit_rate_e,
            "ratio_east_west": visit_ratio_ew,
        },
    },
    "within_effort": {
        "east_north_vs_south": {
            "northeast_observed": ne_obs,
            "northeast_population": ne_pop,
            "east_south_observed": es_obs,
            "east_south_population": es_pop,
            "rate_per_1000": {"northeast": ne_rate, "east_south": es_rate},
            "ratio": ne_es_ratio,
            "ratio_ci95": (ne_es_lo, ne_es_hi),
        },
        "west_north_vs_south": {
            "west_north_observed": wn_obs,
            "west_north_population": wn_pop,
            "west_south_observed": ws_obs,
            "west_south_population": ws_pop,
            "rate_per_1000": {"west_north": wn_rate, "west_south": ws_rate},
            "ratio": wn_ws_ratio,
            "ratio_ci95": (wn_ws_lo, wn_ws_hi),
        },
        "interaction": interaction,
    },
    "decomposition": decomposition,
    "models": model_table.to_dict(orient="records"),
    "lr_test_M6_vs_M6b": lr_test,
    "negative_binomial_M5": nb_res,
    "detection_models": detection.to_dict(orient="records"),
    "row_permutation": perm,
    "rank_info": rank_info,
    "row_bootstrap": bootstrap,
    "leave_one_out": {
        "ne_es_ratio_min": float(loo["ne_es_ratio"].min()),
        "ne_es_ratio_max": float(loo["ne_es_ratio"].max()),
        "ne_es_ratio_rows": loo[loo.kind == "row"][["variant", "ne_es_ratio"]].to_dict(orient="records"),
        "interaction_min": float(loo["interaction"].min()),
        "interaction_max": float(loo["interaction"].max()),
    },
    "area_denominator": area_rates,
    "two_row_bins": two_row_bins.to_dict(orient="records"),
    "moran": moran_out,
}
(OUT / "summary.json").write_text(json.dumps(clean(summary), ensure_ascii=False, indent=2))

# ---------------------------------------------------------------- evidence file
lines = []
lines.append("EVIDENCE: record-vs-occurrence analysis (2026-10-25)")
lines.append(f"n_rows={len(df)} missing=0 zero_observed={int((df.observed==0).sum())} area=1.0 km2")
for k, v in checks.items():
    lines.append(f"check {k}: {v}")
lines.append("")
lines.append("GROUP TOTALS")
for _, r in groups.iterrows():
    lines.append(
        f"{r['group']}: cells={int(r['cells'])} population={int(r['population'])} visits={int(r['visits'])} "
        f"observed={int(r['observed'])} rate_per_1000={r['observed_per_1000_pop']:.6f} per_visit={r['observed_per_visit']:.6f} "
        f"visits_per_1000={r['visits_per_1000_pop']:.6f}"
    )
lines.append("")
lines.append("WEST EAST")
lines.append(f"observed west={obs_w} east={obs_e} ratio={obs_w/obs_e:.6f}")
lines.append(f"population west={pop_w} east={pop_e}")
lines.append(f"visits west={vis_w} east={vis_e} ratio={vis_w/vis_e:.6f}")
lines.append(f"rate_per_1000 west={rate_w:.6f} east={rate_e:.6f} ratio_west_east={rate_ratio_we:.6f} ci95={rate_ratio_we_ci}")
lines.append(f"per_visit west={visit_rate_w:.6f} east={visit_rate_e:.6f} ratio_east_west={visit_ratio_ew:.6f}")
lines.append("")
lines.append("WITHIN EFFORT")
lines.append(f"east north: observed={ne_obs} population={ne_pop} rate_per_1000={ne_rate:.6f}")
lines.append(f"east south: observed={es_obs} population={es_pop} rate_per_1000={es_rate:.6f}")
lines.append(f"NE/ES ratio={ne_es_ratio:.6f} ci95=({ne_es_lo:.6f}, {ne_es_hi:.6f})")
lines.append(f"west north: observed={wn_obs} population={wn_pop} rate_per_1000={wn_rate:.6f}")
lines.append(f"west south: observed={ws_obs} population={ws_pop} rate_per_1000={ws_rate:.6f}")
lines.append(f"WN/WS ratio={wn_ws_ratio:.6f} ci95=({wn_ws_lo:.6f}, {wn_ws_hi:.6f})")
lines.append(f"interaction (EN/ES)/(WN/WS)={interaction:.6f}")
lines.append("")
lines.append("DECOMPOSITION (record rate per person = visits per person x records per visit)")
for k, v in decomposition.items():
    lines.append(f"{k}: {v}")
lines.append("")
lines.append("POISSON MODELS")
for _, r in model_table.iterrows():
    lines.append(
        f"{r['model']}: term={r['term']} rr={r['rr']:.6f} ci95=({r['rr_lo']:.6f},{r['rr_hi']:.6f}) "
        f"p={r['p']:.6g} dispersion={r['dispersion']:.6f} df_resid={r['df_resid']:.1f} aic={r['aic']:.3f}"
    )
lines.append(f"LR test M6 vs M6b: LR={lr_test['lr']:.6f} df={lr_test['df']:.1f} p={lr_test['p']:.6g}")
lines.append(f"NB M5 interaction: {nb_res}")
lines.append("")
lines.append("DETECTION MODELS")
for _, r in detection.iterrows():
    lines.append(str(r.to_dict()))
lines.append("")
lines.append("ROW PERMUTATION")
for k, v in perm.items():
    lines.append(f"{k}: {v}")
lines.append(f"rank info: {rank_info}")
lines.append(f"row bootstrap: {bootstrap}")
lines.append("")
lines.append("LEAVE ONE OUT")
lines.append(f"NE/ES ratio min={loo['ne_es_ratio'].min():.6f} max={loo['ne_es_ratio'].max():.6f}")
lines.append(f"interaction min={loo['interaction'].min():.6f} max={loo['interaction'].max():.6f}")
for _, r in loo[loo.kind == "row"].iterrows():
    lines.append(f"{r['variant']}: NE/ES={r['ne_es_ratio']:.6f} interaction={r['interaction']:.6f}")
lines.append("")
lines.append("AREA DENOMINATOR")
lines.append(str(area_rates))
lines.append("")
lines.append("TWO ROW BINS (east)")
for _, r in two_row_bins.iterrows():
    lines.append(
        f"rows {r['rows']}: observed={int(r['observed'])} population={int(r['population'])} "
        f"rate_per_1000={r['rate_per_1000']:.6f} ratio_vs_last={r['ratio_vs_last']:.6f}"
    )
lines.append("")
lines.append("MORAN")
for k, v in moran_out.items():
    lines.append(f"{k}: rook_k4={v['rook_k4']} queen_k8={v['queen_k8']}")
lines.append("")
lines.append("ROW RATES")
for _, r in row_rates.iterrows():
    lines.append(
        f"row {int(r['row'])} pop={int(r['population_per_cell'])} west_obs={int(r['west_observed'])} east_obs={int(r['east_observed'])} "
        f"west_rate={r['west_rate_per_1000']:.6f} east_rate={r['east_rate_per_1000']:.6f} ratio={r['west_east_ratio']:.6f} "
        f"ratio_ci=({r['west_east_ratio_lo']:.6f},{r['west_east_ratio_hi']:.6f})"
    )
lines.append(
    f"west row rate max/min={row_rates['west_rate_per_1000'].max() / row_rates['west_rate_per_1000'].min():.6f} "
    f"east row rate max/min={row_rates['east_rate_per_1000'].max() / row_rates['east_rate_per_1000'].min():.6f}"
)
(OUT / "evidence.txt").write_text("\n".join(lines), encoding="utf-8")

print("done")
print(json.dumps(clean({k: summary[k] for k in ["west_east", "within_effort", "lr_test_M6_vs_M6b", "row_permutation", "leave_one_out", "area_denominator"]}), ensure_ascii=False, indent=2))
print("font:", FONT)
