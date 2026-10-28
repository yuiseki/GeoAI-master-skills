"""B4: the two permutations of the frozen M5 (retrospective, frozen radius).

F1: the four 2023-2026 mast scarcity values reassigned to the years (all 24 orders); beta refitted on the training
years with the reassigned values, the target scored with its reassigned value. Passes when at most 2 of the 23
non-identity orders reach the true capture@5%.
F2: the exposure surface permuted by 10 km tiles (donors: tiles with at least 90% prefecture cells; every tile with
a prefecture cell receives a donor tile in a shuffled, repeated order; a cell takes the donor's value at the same
offset). 200 times, seed 0, the same permuted surface for training and target, beta refitted. Passes when the
true capture@5% is above the 95th percentile.

    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-mast-exposure/scripts \
      uvx --with numpy --with pandas --with pyarrow --with scikit-learn python falsify.py BEAR_ART ART MAST_CSV OUTDIR
"""

import itertools
import json
import os
import sys

import numpy as np

YEARS = (2023, 2024, 2025, 2026)


def year_permutations(s):
    vals = [s[y] for y in YEARS]
    return [dict(zip(YEARS, p)) for p in itertools.permutations(vals)]


def tiles(inside, size=100, min_share=0.9):
    ny, nx = inside.shape
    donors, targets = [], []
    for ti in range((ny + size - 1) // size):
        for tj in range((nx + size - 1) // size):
            blk = inside[ti * size:(ti + 1) * size, tj * size:(tj + 1) * size]
            if blk.any():
                targets.append((ti, tj))
            if blk.shape == (size, size) and blk.mean() >= min_share:
                donors.append((ti, tj))
    return donors, targets


def permute_tiles(field, inside, rng, size=100, min_share=0.9):
    donors, targets = tiles(inside, size, min_share)
    order = [donors[i] for i in rng.permutation(len(donors))]
    out = np.zeros_like(field)
    for k, (ti, tj) in enumerate(targets):
        di, dj = order[k % len(order)]
        h = min(size, field.shape[0] - ti * size)
        w = min(size, field.shape[1] - tj * size)
        out[ti * size:ti * size + h, tj * size:tj * size + w] = field[di * size:di * size + h, dj * size:dj * size + w]
    return out


def main():
    import data
    import evaluate as ev
    import metrics as mt
    from run_confirm import SPEC_SHA

    bear, art, mast_csv, outdir = sys.argv[1:5]
    out = f"{outdir}/b4_falsification.json"
    if os.path.exists(out):
        raise SystemExit(f"{out} exists")
    spec_path = f"{outdir}/b1_frozen_spec.json"
    if data.sha256(spec_path) != SPEC_SHA:
        raise SystemExit("the frozen specification changed")
    spec = json.load(open(spec_path))
    d = data.load(bear, art)
    muni = d["muni"]
    inside = muni >= 0
    name = spec["features"]["M5"]
    field = np.nan_to_num(np.asarray(d["exposure"][name], dtype=float), nan=0.0)
    e = data.vec(field, muni)
    s = data.read_mast(mast_csv, "fruiting")

    def cap(e_, s_, target):
        o = ev.run(d["benv"][target], e_, s_, d["counts"], data.TRAIN[target], target, score_only=True)
        return mt.capture(mt.rank_order(o["score"]), d["counts"][target] > 0, 0.05), o["fit"]["beta"]

    res = {"spec_sha256": SPEC_SHA, "feature": name, "F1_year": {}, "F2_spatial": {}}
    perms = year_permutations(s)
    for target in (2025, 2026):
        vals = [cap(e, p, target) for p in perms]
        true = vals[0][0]
        reach = sum(v[0] >= true - 1e-12 for v in vals[1:])
        res["F1_year"][target] = {"true": true, "perm_values": [v[0] for v in vals[1:]], "perm_betas": [v[1] for v in vals[1:]],
                                  "orders": [list(p.values()) for p in perms[1:]], "n_reach_true": reach, "passes": reach <= 2}
        print("F1", target, true, reach, flush=True)
    donors, targets = tiles(inside)
    rng = np.random.default_rng(0)
    pv = {2025: [], 2026: []}
    for i in range(200):
        ep = data.vec(permute_tiles(field, inside, rng), muni)
        for target in (2025, 2026):
            pv[target].append(cap(ep, s, target)[0])
        if i % 20 == 0:
            print("F2", i, flush=True)
    for target in (2025, 2026):
        true = cap(e, s, target)[0]
        v = np.array(pv[target])
        res["F2_spatial"][target] = {"true": true, "perm_values": v.tolist(), "perm_median": float(np.median(v)), "perm_p95": float(np.quantile(v, 0.95)),
                                     "share_ge_true": float((v >= true - 1e-12).mean()), "passes": bool(true > np.quantile(v, 0.95))}
    res["F2_spatial"]["tiles"] = {"donors": len(donors), "targets": len(targets)}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: {t: {kk: vv for kk, vv in v.items() if "values" not in kk and "betas" not in kk and kk != "orders"} if isinstance(v, dict) else v
                          for t, v in r.items()} for k, r in res.items() if k.startswith("F")}, indent=1))


if __name__ == "__main__":
    main()
