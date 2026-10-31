"""Post-hoc look at the year shift (added after R005 and R006; exploratory, see EXPERIMENT_PLAN.md 計画の変更).

On the same common axes as interface_year_shift.py (fitted on the two other years) and April-September positives:
(1) the 25-bin composition with bins cut at percentiles 0.50, 0.80, 0.90 and 0.95 of each axis, and the JSD of two
years' compositions; (2) the level m = (b + h) / 2 and the lean d = b - h of each positive cell, compared by Cliff's
delta. F3 swaps the year labels of whole 10 km blocks (1,000 times, seed 0) for the p of every statistic.

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      uvx --with numpy==2.5.4 --with scipy --with pandas --with pyarrow python \
      projects/_bear/akita-bear-human-interface/scripts/interface_shift_posthoc.py \
      artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-human-interface \
      projects/_bear/akita-bear-human-interface/outputs/year_shift_posthoc.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

import interface_models as im
import phase as ph
from interface_phase_space import YEAR_AXIS, positives
from interface_year_shift import ADJACENT, YEARS, axis_file


def stats(pb, phh, later):
    e = ~later
    ce, cl = np.zeros((5, 5)), np.zeros((5, 5))
    bb, hb = ph.cut_bins(pb), ph.cut_bins(phh)
    np.add.at(ce, (bb[e] - 1, hb[e] - 1), 1)
    np.add.at(cl, (bb[later] - 1, hb[later] - 1), 1)
    m, d = (pb + phh) / 2, pb - phh
    return {"jsd_top_bins": ph.jsd(ce, cl), "cliff_level": ph.cliffs_delta(m[later], m[e]),
            "cliff_lean": ph.cliffs_delta(d[later], d[e])}


def top_bin_shares(pb, phh, mask):
    c = np.zeros((5, 5))
    np.add.at(c, (ph.cut_bins(pb[mask]) - 1, ph.cut_bins(phh[mask]) - 1), 1)
    return (c / c.sum()).round(6).tolist()


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("out", type=Path)
    a.add_argument("--perm", type=int, default=1000)
    args = a.parse_args()
    im.check_inputs(args.art)
    inside = np.load(args.art / "grid_mask.npz")["muni"] >= 0
    pos = positives(args.art, args.work, inside)["apr_sep"]
    block = im.blocks_10km(args.art)
    rng = np.random.default_rng(0)
    res = {"mode": "post-hoc exploratory (after R005, R006)", "cuts": list(ph.TOP_CUTS),
           "bins_index": "[b band - 1][h band - 1], band 1 below 0.50 ... band 5 above 0.95", "years": {}, "pairs": {}}
    for y, (f, note) in YEAR_AXIS.items():
        z = np.load(args.work / "scores" / f)
        pb, phh = ph.percentile(z["M_B"].astype(float)), ph.percentile(z["M_H"].astype(float))
        allc = np.ones(len(pb), bool)
        res["years"][str(y)] = {"axis": f, "axis_note": note, "pos_shares": top_bin_shares(pb, phh, pos[y]),
                                "cell_shares": top_bin_shares(pb, phh, allc),
                                "level": ph.summary(((pb + phh) / 2)[pos[y]]), "lean": ph.summary((pb - phh)[pos[y]])}
    for i, ea in enumerate(YEARS):
        for eb in YEARS[i + 1:]:
            f = axis_file(ea, eb)
            z = np.load(args.work / "scores" / f)
            pb, phh = ph.percentile(z["M_B"].astype(float)), ph.percentile(z["M_H"].astype(float))
            idx = np.concatenate([np.flatnonzero(pos[ea]), np.flatnonzero(pos[eb])])
            later = np.r_[np.zeros(pos[ea].sum(), bool), np.ones(pos[eb].sum(), bool)]
            b_, h_, blk = pb[idx], phh[idx], block[idx]
            obs = stats(b_, h_, later)
            nb = len(np.unique(blk))
            null = [stats(b_, h_, ph.block_flip(later, blk, rng.random(nb) < 0.5)) for _ in range(args.perm)]
            p = {k: float(np.mean(np.abs([n[k] for n in null]) >= abs(obs[k]))) for k in obs}
            row = {"axis": f, "adjacent": (ea, eb) in ADJACENT, **obs, "f3_block_p": p,
                   "earlier_level": ph.summary(((b_ + h_) / 2)[~later]), "later_level": ph.summary(((b_ + h_) / 2)[later]),
                   "earlier_lean": ph.summary((b_ - h_)[~later]), "later_lean": ph.summary((b_ - h_)[later])}
            res["pairs"][f"{ea}_to_{eb}"] = row
            print(f"{ea}->{eb}: level {obs['cliff_level']:+.3f} (p {p['cliff_level']:.3f}) lean {obs['cliff_lean']:+.3f} "
                  f"(p {p['cliff_lean']:.3f}) jsd_top {obs['jsd_top_bins']:.4f} (p {p['jsd_top_bins']:.3f}) | median lean "
                  f"{row['earlier_lean']['median']:+.4f} -> {row['later_lean']['median']:+.4f}", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
