"""B1: development-period choice (EXPERIMENT_PLAN.md). Uses only target years 1990-1999 and ranks up to 1999; the
confirmation rows (t >= 2000) are dropped before anything is computed.

Chooses the terrain radius r (300, 1000) and the water form (w1: WB, w2: P + PET) by the C-scheme RMSE of M5, then
G* (M4 or M5) by the C-scheme RMSE. Writes outputs/b1_dev_scores.json and outputs/b1_frozen_choice.json; stops if
the choice file exists.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj python \
      projects/_bear/beech-masting-spatial-proxy/scripts/run_dev.py projects/_bear/beech-masting-spatial-proxy/outputs
"""

import argparse
import hashlib
import json
from pathlib import Path

import model as M
import rows as R

DEV = list(range(1990, 2000))
VARIANTS = [(r, w) for r in (300, 1000) for w in ("w1", "w2")]
MODELS = ["M0", "M1", "M2", "M3", "M4", "M5", "M7"]


def score_all(pred, models):
    err = M.common_rows(M.row_errors(pred), models)
    return M.scores(err)


def choose(c_rmse):
    """c_rmse: {(r, w): {"M4": rmse, "M5": rmse}}. Smallest M5; ties (< 0.001) prefer r = 1000, then w1.
    Then G*: M5 if its RMSE is at least 0.001 below M4's, else M4."""
    best = min(c_rmse.values(), key=lambda v: v["M5"])["M5"]
    tied = [k for k, v in c_rmse.items() if v["M5"] - best < 0.001]
    tied.sort(key=lambda k: (k[0] != 1000, k[1] != "w1"))
    r, w = tied[0]
    v = c_rmse[(r, w)]
    g = "M5" if v["M5"] < v["M4"] - 0.001 else "M4"
    return {"radius": r, "water": w, "g_star": g}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    out_choice = a.outputs / "b1_frozen_choice.json"
    if out_choice.exists():
        raise SystemExit(f"{out_choice} exists: B1 is frozen")
    ranks, climate, terrain, sites = R.load(a.outputs)
    ranks = ranks[ranks.year <= 1999]
    result, c_rmse = {}, {}
    for r, w in VARIANTS:
        rows = R.build(ranks, climate, terrain, sites, r)
        rows = rows[rows.t.isin(DEV)]
        assert rows.t.max() <= 1999
        res = {"A": score_all(M.run_A(rows, DEV, DEV, MODELS, w), MODELS),
               "B": score_all(M.run_BC(rows, ranks, sites, "B", DEV, DEV, MODELS + ["M1y"], w), MODELS + ["M1y"]),
               "C": score_all(M.run_BC(rows, ranks, sites, "C", DEV, DEV, MODELS, w), MODELS)}
        result[f"r{r}_{w}"] = res
        c_rmse[(r, w)] = {m: res["C"][m]["rmse"] for m in ("M4", "M5")}
        print(r, w, {s: {m: round(v["rmse"], 4) for m, v in res[s].items()} for s in res}, flush=True)
    choice = choose(c_rmse)
    (a.outputs / "b1_dev_scores.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    body = json.dumps({**choice, "rule": "min C-scheme RMSE of M5 over 4 variants; G* = M5 if 0.001 below M4",
                       "dev_targets": [DEV[0], DEV[-1]], "c_rmse": {f"r{k[0]}_{k[1]}": v for k, v in c_rmse.items()}},
                      indent=1) + "\n"
    out_choice.write_text(body, encoding="utf-8")
    print(body, "sha256", hashlib.sha256(body.encode()).hexdigest())


if __name__ == "__main__":
    main()
