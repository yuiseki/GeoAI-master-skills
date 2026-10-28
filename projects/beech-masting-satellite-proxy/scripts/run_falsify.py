"""B4 falsification on the confirmation years, scheme C, model S2 (EXPERIMENT_PLAN.md). Runs whatever B3 found.

    F1 year permutation: every site's four anomalies of year t come from year pi(t) (one pi for all sites)
    F2 site permutation within year: in each year the four anomalies of a site come from another site of that year

200 permutations each (seed 0). Each permutation is compared with the real predictions on the rows it scores
(rows may drop when the permuted anomaly is missing). Passes if the real within-year Spearman is above the 95th
percentile of the permutations (the median of the paired real values is compared). Writes outputs/b4_falsification.json; stops if it exists.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj --with pyarrow python \
      projects/beech-masting-satellite-proxy/scripts/run_falsify.py projects/beech-masting-satellite-proxy/outputs \
      artifacts/beech-masting-satellite-proxy
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import model as M
import rows as R
from run_confirm import ALL, CONF, load_spec

PERMS = 200


def within_on(real_rows, keys):
    r = real_rows.merge(keys, on=["ID", "t"])
    return M.within_year(r)["mean"]


def summary(real, perm):
    real, perm = np.array(real), np.array(perm)
    return {"real_mean_over_perms": float(real.mean()), "perm_p95": float(np.percentile(perm, 95)),
            "perm_median": float(np.median(perm)), "share_perm_at_least_real": float(np.mean(perm >= real)),
            "real_minus_perm_median": float(np.median(real - perm)),
            "passes": bool(np.median(real) > np.percentile(perm, 95)), "perms": len(perm)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    ap.add_argument("art", type=Path)
    a = ap.parse_args()
    spec, spec_sha = load_spec(a.outputs)
    out_path = a.outputs / "b4_falsification.json"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists")
    rows, ranks, sites, raw, prov = R.load(a.outputs)
    k = spec["coverage_rule"]["min_years"]
    pred = pd.read_parquet(a.art / "confirm_predictions.parquet")
    real_rows = M.row_means(pred[(pred.scheme == "C") & (pred.model == "S2")])
    real_all = M.within_year(real_rows)["mean"]
    cache = {}
    rng = np.random.default_rng(0)
    res = {"spec_sha256": spec_sha, "real_within_year_spearman_S2_C": real_all}
    for name, make in (("F1_year", lambda: M.year_permutation(ALL, rng)),
                       ("F2_site_within_year", lambda: M.site_permutation(raw, rng))):
        real, perm, rows_n = [], [], []
        for i in range(PERMS):
            p = M.run_BC(rows, raw, ranks, sites, "C", CONF, ALL, ["S2"], k, transform=make(), lag_cache=cache)
            pr = M.row_means(p)
            perm.append(M.within_year(pr)["mean"])
            real.append(within_on(real_rows, pr[["ID", "t"]]))
            rows_n.append(len(pr))
            if i % 20 == 0:
                print(name, i, round(real[-1], 4), round(perm[-1], 4), len(pr), flush=True)
        res[name] = {**summary(real, perm), "rows_min": int(min(rows_n)), "rows_max": int(max(rows_n)),
                     "real_rows": len(real_rows), "perm_values": [round(x, 5) for x in perm]}
        print(name, {k2: v for k2, v in res[name].items() if k2 != "perm_values"}, flush=True)
    out_path.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
