"""Seasonal satellite values per site and target year (EXPERIMENT_PLAN.md), from the frozen Landsat 5 table and
the frozen coverage rule (outputs/coverage_rule.json). Reads no outcome.

    ndvi_ps, ndmi_ps: median over the usable acquisitions of July-August of t - 1 (previous summer)
    ndvi_cs, ndmi_cs: median over the usable acquisitions of April-May of t (current spring)

An acquisition is usable if it is the one kept for its site and date, its tier is in the rule and it has at least
min_valid valid pixels; a season needs min_scenes usable acquisitions, otherwise its values are missing. The
anomalies are made later, inside each fold (model.py).

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy python \
      projects/beech-masting-satellite-proxy/scripts/features.py projects/beech-masting-satellite-proxy/outputs
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

TARGETS = range(1990, 2009)


def seasonal(acq, rule):
    a = acq[acq.kept_for_site_date & acq.tier.isin(rule["tiers"]) & (acq.n_valid >= rule["min_valid"])].copy()
    a["t"] = np.where(a.season == "summer", a.year + 1, a.year)
    a["w"] = np.where(a.season == "summer", "ps", "cs")
    g = a.groupby(["ID", "t", "w"]).agg(ndvi=("ndvi", "median"), ndmi=("ndmi", "median"), n=("ndvi", "size"))
    full = pd.MultiIndex.from_product([sorted(acq.ID.unique()), TARGETS, ["ps", "cs"]], names=["ID", "t", "w"])
    g = g.reindex(full)
    g["n"] = g.n.fillna(0).astype(int)
    g.loc[g.n < rule["min_scenes"], ["ndvi", "ndmi"]] = np.nan
    w = g.unstack("w")
    out = pd.DataFrame({"ID": w.index.get_level_values("ID"), "t": w.index.get_level_values("t"),
                        "ndvi_ps": w[("ndvi", "ps")].to_numpy(), "ndmi_ps": w[("ndmi", "ps")].to_numpy(),
                        "ndvi_cs": w[("ndvi", "cs")].to_numpy(), "ndmi_cs": w[("ndmi", "cs")].to_numpy(),
                        "n_ps": w[("n", "ps")].to_numpy(), "n_cs": w[("n", "cs")].to_numpy()})
    return out.reset_index(drop=True)


def main():
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    rule = json.loads((a.outputs / "coverage_rule.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    con.sql("install httpfs; load httpfs")
    acq = con.sql(f"select * from 'hf://datasets/{rule['dataset']}@{rule['revision']}/data/site_acquisitions.parquet'").df()
    out = seasonal(acq, rule)
    out.to_csv(a.outputs / "satellite_seasonal.csv", index=False, float_format="%.6f")
    sat = ["ndvi_ps", "ndmi_ps", "ndvi_cs", "ndmi_cs"]
    print(json.dumps({"rows": len(out), "sites": int(out.ID.nunique()),
                      "non_missing": out[sat].notna().sum().to_dict(),
                      "rows_all_four": int(out[sat].notna().all(axis=1).sum()),
                      "describe": out[sat].describe().round(4).to_dict()}, indent=1, default=int))


if __name__ == "__main__":
    main()
