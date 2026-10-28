"""B0 for the rows and the splits: row counts by target year and lag, blocks, and per fold the test sites, training
sites and sites left out by the 15 km buffer. Reads no model result.

From repository root:
    uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj python \
      projects/_bear/beech-masting-spatial-proxy/scripts/splits.py projects/_bear/beech-masting-spatial-proxy/outputs
"""

import argparse
import json
from pathlib import Path

import model as M
import rows as R


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    a = ap.parse_args()
    ranks, climate, terrain, sites = R.load(a.outputs)
    rows = R.build(ranks, climate, terrain, sites, 1000)
    by_t = rows.groupby("t").agg(rows=("y", "size"), own_lag=("lag_own", lambda s: int(s.notna().sum())))
    b = M.blocks(sites)
    folds = []
    for r in range(M.REPEATS):
        for f, (test, train) in enumerate(M.spatial_folds(sites, r)):
            folds.append({"repeat": r, "fold": f, "test_sites": len(test), "train_sites": len(train),
                          "buffer_left_out": len(sites) - len(test) - len(train)})
    out = {"ranks_valid_tohoku": len(ranks), "ranks_by_year": ranks.groupby("year").size().to_dict(),
           "rows_t_1990_2008": len(rows), "by_t": by_t.to_dict(orient="index"),
           "dev_rows": int((rows.t <= 1999).sum()), "confirm_rows": int((rows.t >= 2000).sum()),
           "blocks": int(b.nunique()), "sites_per_block": b.value_counts().describe().round(2).to_dict(),
           "folds": folds,
           "fold_summary": {k: [min(f[k] for f in folds), max(f[k] for f in folds)]
                            for k in ("test_sites", "train_sites", "buffer_left_out")}}
    (a.outputs / "splits_audit.json").write_text(json.dumps(out, indent=1, default=int) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "folds"}, indent=1, default=int))


if __name__ == "__main__":
    main()
