"""B2 and B3: the frozen models of B1 on the confirmation years (target years 2009-2026), once.

B2: RMSE of the chosen model against M0 and M1, with a 90% interval from resampling years (all prefectures of a
year together; 2,000, seed 0). B3: F1 the placebo (summer of t+1 for t-1; t <= 2025) against M0; F2 the chosen
model with the weather cues of whole years permuted (2,000, seed 0); F3 the within-year slope of the prefecture's
deviation of the index on its deviation of Ts(t-1) (exploratory).

From repository root:
    uvx --with pandas --with scipy python projects/_bear/beech-masting-triggers/scripts/confirm_b2.py \
      projects/_bear/beech-masting-triggers/outputs
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import models as md

CONFIRM = (2009, 2026)
FROZEN_SHA = "806b92fa8faebc7d4ddfc84a3e028fc7b70a12db745b7a5b7e049c88ab340fc9"
WEATHER_CUES = ["Ts_lag1", "Ts_lag2", "Tsp", "dT"]


def interval(a, b, q=(.05, .95)):
    d = np.asarray(a) - np.asarray(b)
    return [float(np.quantile(d, q[0])), float(np.quantile(d, q[1]))]


def permute_years(df, cols, rng):
    """The same rows with the weather cues of each year replaced by those of another year (a permutation of
    years; the prefectures of a year move together)."""
    years = np.array(sorted(df.year.unique()))
    to = dict(zip(years, rng.permutation(years)))
    src = df.set_index(["pref", "year"])[cols]
    out = df.copy()
    out[cols] = np.vstack([src.loc[(p, to[y])].to_numpy() for p, y in zip(df.pref, df.year)])
    return out


def within_year(df, x, y="F"):
    """Slope of the deviation of y from its year mean on the deviation of x from its year mean."""
    dx = df[x] - df.groupby("year")[x].transform("mean")
    dy = df[y] - df.groupby("year")[y].transform("mean")
    return float((dx * dy).sum() / (dx * dx).sum())


def classes(v):
    return np.digitize(v, [1.0, 2.0, 3.5])  # 大凶作, 凶作, 並作, 豊作


def main():
    from scipy.stats import spearmanr

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()
    out = a.outputs / "b2_b3_confirm.json"
    if out.exists():
        raise ValueError("already run once")
    fz_path = a.outputs / "b1_frozen_models.json"
    if hashlib.sha256(fz_path.read_bytes()).hexdigest() != FROZEN_SHA:
        raise ValueError("the frozen models changed")
    b1 = json.loads(fz_path.read_text(encoding="utf-8"))
    fz, chosen = b1["frozen"], b1["chosen"]
    index = pd.read_csv(a.outputs / "tohoku_beech_index.csv")
    cues = pd.read_csv(a.outputs / "cues_weather.csv")
    d = md.design(index, cues)
    test = md.complete_rows(d[d.year.between(*CONFIRM)])
    dev = md.complete_rows(d[d.year.between(1990, 2008)])
    preds = {k: md.predict(fz[k], test) for k in ("M0", "M1", chosen)}
    rmse = {k: md.rmse(test.F, p) for k, p in preds.items()}
    boot = md.year_bootstrap(test, preds, B=a.boot, seed=0)
    vs = {k: {"diff": rmse[chosen] - rmse[k], "ci90": interval(boot[chosen], boot[k])} for k in ("M0", "M1")}
    if all(v["ci90"][1] < 0 for v in vs.values()):
        verdict = "supported"
    elif any(v["diff"] > 0 for v in vs.values()):
        verdict = "rejected"
    else:
        verdict = "undetermined"

    # auxiliary: every candidate refitted on the development rows, Spearman, classes, a rolling refit
    aux = {}
    for name, feats in md.CANDIDATES.items():
        p = md.predict(md.fit(dev, feats), test)
        aux[name] = {"rmse": md.rmse(test.F, p), "spearman": float(spearmanr(test.F, p)[0]),
                     "class_hit": float(np.mean(classes(p) == classes(test.F)))}
    rolling = np.empty(len(test))
    for y in sorted(test.year.unique()):
        past = md.complete_rows(d[(d.year >= 1990) & (d.year < y)])
        rows = (test.year == y).to_numpy()
        rolling[rows] = md.predict(md.fit(past, md.CANDIDATES[chosen]), test[rows])
    rolling_m1 = np.empty(len(test))
    for y in sorted(test.year.unique()):
        past = md.complete_rows(d[(d.year >= 1990) & (d.year < y)])
        rows = (test.year == y).to_numpy()
        rolling_m1[rows] = md.predict(md.fit(past, md.CANDIDATES["M1"]), test[rows])

    # F1 placebo: t <= 2025 (the summer of 2026 is not in the data yet)
    tp = test[test.year <= 2025].dropna(subset=fz["placebo"]["features"]).reset_index(drop=True)
    pp = {"placebo": md.predict(fz["placebo"], tp), "M0": md.predict(fz["M0"], tp), chosen: md.predict(fz[chosen], tp)}
    bp = md.year_bootstrap(tp, pp, B=a.boot, seed=0)
    f1 = {"rows": len(tp), "rmse": {k: md.rmse(tp.F, v) for k, v in pp.items()},
          "placebo_minus_M0": md.rmse(tp.F, pp["placebo"]) - md.rmse(tp.F, pp["M0"]),
          "ci90": interval(bp["placebo"], bp["M0"])}

    # F2 permutation of years of the weather cues
    rng = np.random.default_rng(0)
    perm = np.array([md.rmse(test.F, md.predict(fz[chosen], permute_years(test, WEATHER_CUES, rng)))
                     for _ in range(a.boot)])
    f2 = {"observed_rmse": rmse[chosen], "perm_q05": float(np.quantile(perm, .05)),
          "perm_median": float(np.median(perm)), "share_perm_le_observed": float(np.mean(perm <= rmse[chosen])),
          "passes": bool(rmse[chosen] < np.quantile(perm, .05))}

    # F3 within-year slope (exploratory)
    rs = np.random.default_rng(0)
    years = np.array(sorted(test.year.unique()))
    slopes = []
    for _ in range(a.boot):
        pick = rs.choice(years, len(years))
        sample = pd.concat([test[test.year == y].assign(year=i) for i, y in enumerate(pick)])
        slopes.append(within_year(sample, "Ts_lag1"))
    f3 = {"slope": within_year(test, "Ts_lag1"), "ci90": [float(np.quantile(slopes, .05)), float(np.quantile(slopes, .95))],
          "slope_dev_period": within_year(dev, "Ts_lag1")}

    result = {"blocks": ["B2", "B3"], "frozen_sha256": FROZEN_SHA, "chosen": chosen,
              "rows": len(test), "years": [int(test.year.min()), int(test.year.max())], "n_years": int(test.year.nunique()),
              "B2": {"rmse": rmse, "chosen_vs": vs, "verdict": verdict},
              "auxiliary": {"refit_on_dev": aux, "rolling_refit_rmse": {chosen: md.rmse(test.F, rolling),
                                                                         "M1": md.rmse(test.F, rolling_m1)}},
              "B3": {"F1_placebo": f1, "F2_permute_years": f2, "F3_within_year": f3},
              "per_row": [{"year": int(r.year), "pref": r.pref, "F": float(r.F),
                           **{k: round(float(preds[k][i]), 3) for k in preds}} for i, r in enumerate(test.itertuples())]}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_row"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
