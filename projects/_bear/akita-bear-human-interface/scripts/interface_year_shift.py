"""Where the positive cells of two bear years sit in the phase space, on a common axis fitted on neither year
(the other two of 2023-2026), and how far that differs from swapping the year labels (F3).

For each pair: the bear-side and human-side percentiles of each year's positive cells (quartiles), Cliff's delta
(later - earlier) and KS on each axis, the JSD of the 25-bin compositions and the region shares. F3 swaps the year
labels of whole 10 km blocks with probability 1/2 (1,000 times, seed 0); the two-sided p is the share of swaps with
|statistic| at least the observed one. A cell-level swap (ignores spatial dependence, too lenient) is shown beside it.
Direction rule (EXPERIMENT_PLAN.md): an axis moved only if |Cliff's delta| >= 0.147 and the block-swap p < 0.05.

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      uvx --with numpy==2.5.4 --with scipy --with pandas --with pyarrow python \
      projects/_bear/akita-bear-human-interface/scripts/interface_year_shift.py \
      artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-human-interface \
      projects/_bear/akita-bear-human-interface/outputs/year_shift.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

import interface_models as im
import phase as ph
from interface_phase_space import positives

YEARS = (2023, 2024, 2025, 2026)
ADJACENT = ((2023, 2024), (2024, 2025), (2025, 2026))
EFFECT = 0.147
ALPHA = 0.05


def axis_file(a, b):
    other = [y for y in YEARS if y not in (a, b)]
    if other == [2023, 2024]:
        return "b2_confirm_2023-2024_to_2025.npz"  # the B2 models: trained on 2023+2024
    return f"axes_{other[0]}-{other[1]}.npz"


def direction(cliff, p):
    if abs(cliff) >= EFFECT and p < ALPHA:
        return "higher" if cliff > 0 else "lower"
    return "no clear move"


def reading(db, dh):
    return {("higher", "lower"): "toward higher bear-side proxy and lower human-side proxy",
            ("lower", "higher"): "toward higher human-side proxy and lower bear-side proxy",
            ("higher", "higher"): "toward higher values of both proxies",
            ("lower", "lower"): "toward lower values of both proxies"}.get(
        (db, dh), f"bear-side: {db}; human-side: {dh}")


def compare(pb, phh, bq, hq, block, ea, la, n_perm, rng):
    """ea, la: positive masks of the earlier and the later year."""
    from scipy.stats import ks_2samp

    idx = np.concatenate([np.flatnonzero(ea), np.flatnonzero(la)])
    later = np.r_[np.zeros(ea.sum(), bool), np.ones(la.sum(), bool)]
    eb, ehh, ebq, ehq, blk = pb[idx], phh[idx], bq[idx], hq[idx], block[idx]
    obs = ph.pair_stats(eb, ehh, later, ebq, ehq)
    nblocks = len(np.unique(blk))
    null_block = [ph.pair_stats(eb, ehh, ph.block_flip(later, blk, rng.random(nblocks) < 0.5), ebq, ehq)
                  for _ in range(n_perm)]
    null_cell = [ph.pair_stats(eb, ehh, rng.permutation(later), ebq, ehq) for _ in range(n_perm)]

    def p(null, k, two_sided=True):
        v = np.array([n[k] for n in null])
        return float(np.mean(np.abs(v) >= abs(obs[k]))) if two_sided else float(np.mean(v >= obs[k]))

    out = {"earlier": {"b_pct": ph.summary(pb[ea]), "h_pct": ph.summary(phh[ea]), "regions": ph.region_shares(bq, hq, ea)},
           "later": {"b_pct": ph.summary(pb[la]), "h_pct": ph.summary(phh[la]), "regions": ph.region_shares(bq, hq, la)},
           "cliff_b": obs["cliff_b"], "cliff_h": obs["cliff_h"], "jsd_bins": obs["jsd"],
           "ks_b": float(ks_2samp(pb[la], pb[ea]).statistic), "ks_h": float(ks_2samp(phh[la], phh[ea]).statistic),
           "f3_block": {"p_cliff_b": p(null_block, "cliff_b"), "p_cliff_h": p(null_block, "cliff_h"),
                        "p_jsd": p(null_block, "jsd", False),
                        "null_jsd_median": float(np.median([n["jsd"] for n in null_block])),
                        "null_cliff_b_95": float(np.quantile(np.abs([n["cliff_b"] for n in null_block]), 0.95)),
                        "null_cliff_h_95": float(np.quantile(np.abs([n["cliff_h"] for n in null_block]), 0.95))},
           "f3_cell": {"p_cliff_b": p(null_cell, "cliff_b"), "p_cliff_h": p(null_cell, "cliff_h"),
                       "p_jsd": p(null_cell, "jsd", False)}}
    out["region_change"] = {r: out["later"]["regions"][r] - out["earlier"]["regions"][r] for r in ph.REGIONS}
    out["direction_b"] = direction(out["cliff_b"], out["f3_block"]["p_cliff_b"])
    out["direction_h"] = direction(out["cliff_h"], out["f3_block"]["p_cliff_h"])
    out["reading"] = reading(out["direction_b"], out["direction_h"])
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("out", type=Path)
    a.add_argument("--perm", type=int, default=1000)
    args = a.parse_args()
    im.check_inputs(args.art)
    inside = np.load(args.art / "grid_mask.npz")["muni"] >= 0
    pos = positives(args.art, args.work, inside)
    block = im.blocks_10km(args.art)
    res = {"derived": "descriptive positions of report cells on model-score axes; not a causal test",
           "rule": {"effect": EFFECT, "alpha": ALPHA, "perm": args.perm, "seed": 0}, "pairs": {}}
    rng = np.random.default_rng(0)
    for i, ea in enumerate(YEARS):
        for eb in YEARS[i + 1:]:
            f = axis_file(ea, eb)
            z = np.load(args.work / "scores" / f)
            pb, phh = ph.percentile(z["M_B"].astype(float)), ph.percentile(z["M_H"].astype(float))
            bq, hq = ph.quintile(pb), ph.quintile(phh)
            row = {"axis": f, "axis_sha256": im.sha256(args.work / "scores" / f), "adjacent": (ea, eb) in ADJACENT}
            for kind, d in pos.items():
                if ea in d and eb in d:
                    row[kind] = compare(pb, phh, bq, hq, block, d[ea], d[eb], args.perm, rng)
                    r = row[kind]
                    print(f"{ea}->{eb} {kind} axis {f}: cliff_b {r['cliff_b']:+.3f} (p {r['f3_block']['p_cliff_b']:.3f}) "
                          f"cliff_h {r['cliff_h']:+.3f} (p {r['f3_block']['p_cliff_h']:.3f}) jsd {r['jsd_bins']:.4f} "
                          f"(p {r['f3_block']['p_jsd']:.3f}) | {r['reading']}", flush=True)
            res["pairs"][f"{ea}_to_{eb}"] = row
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
