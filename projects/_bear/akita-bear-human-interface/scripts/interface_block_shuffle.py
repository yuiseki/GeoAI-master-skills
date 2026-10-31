"""F2, spatial block shuffle: move each year's April-September positive cells, 10 km block by 10 km block (keeping
their places inside the block), to another block at random (200 times, seed 0), and see how much of the phase-space
concentration is left. Cells that land outside the prefecture are dropped and counted.

Statistics per year, on that year's axes (interface_phase_space.YEAR_AXIS): the JSD between the positives' and all
cells' 25-bin compositions (equal quintiles), the share in the contact region, and the median level (b + h) / 2.

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      uvx --with numpy==2.5.4 --with scipy --with pandas --with pyarrow python \
      projects/_bear/akita-bear-human-interface/scripts/interface_block_shuffle.py \
      artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-human-interface \
      projects/_bear/akita-bear-human-interface/outputs/f2_block_shuffle.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

import interface_models as im
import phase as ph
from interface_phase_space import YEAR_AXIS, positives

N = 200
SIZE = 100  # cells: 10 km


def stats(bq, hq, level, mask):
    allc = ph.bin_counts(bq, hq, np.ones(len(bq), bool))
    return {"jsd_pos_vs_cells": ph.jsd(ph.bin_counts(bq, hq, mask), allc),
            "contact_share": ph.region_shares(bq, hq, mask)["contact"],
            "median_level": float(np.median(level[mask]))}


def main():
    import pandas as pd

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("out", type=Path)
    args = a.parse_args()
    im.check_inputs(args.art)
    inside = np.load(args.art / "grid_mask.npz")["muni"] >= 0
    cells = pd.read_parquet(args.art / "cells.parquet", columns=["ix", "iy"])
    ix, iy = cells.ix.to_numpy(), cells.iy.to_numpy()
    blocks = sorted(set(zip((ix // SIZE).tolist(), (iy // SIZE).tolist())))
    pos = positives(args.art, args.work, inside)["apr_sep"]
    rng = np.random.default_rng(0)
    res = {"derived": "falsification on shuffled report cells", "n_shuffles": N, "block_cells": SIZE, "seed": 0,
           "n_blocks": len(blocks), "years": {}}
    for y, (f, _) in YEAR_AXIS.items():
        z = np.load(args.work / "scores" / f)
        pb, phh = ph.percentile(z["M_B"].astype(float)), ph.percentile(z["M_H"].astype(float))
        bq, hq, level = ph.quintile(pb), ph.quintile(phh), (pb + phh) / 2
        obs = stats(bq, hq, level, pos[y])
        null, kept = [], []
        for _ in range(N):
            m = ph.block_shuffle(ix, iy, pos[y], SIZE, ph.random_block_perm(blocks, rng))
            kept.append(int(m.sum()))
            null.append(stats(bq, hq, level, m))
        q = {k: {p: float(np.quantile([n[k] for n in null], p)) for p in (0.05, 0.5, 0.95)} for k in obs}
        res["years"][str(y)] = {"axis": f, "observed": obs, "null": q, "n_pos": int(pos[y].sum()),
                                "kept_median": float(np.median(kept)),
                                "p_jsd_null_ge_obs": float(np.mean([n["jsd_pos_vs_cells"] >= obs["jsd_pos_vs_cells"] for n in null]))}
        print(y, {k: round(v, 4) for k, v in obs.items()}, "null median", {k: round(v[0.5], 4) for k, v in q.items()},
              "kept", np.median(kept), "/", int(pos[y].sum()), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
