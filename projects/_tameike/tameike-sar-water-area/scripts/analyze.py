"""B0, B1, B2 of EXPERIMENT_PLAN.md from the cached scenes (fetch_scenes.py) and pond outlines (build_masks.py).

  systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
    uvx --python 3.12 --with numpy --with scipy --with rasterio python scripts/analyze.py

Writes outputs/b0.json, artifacts/_tameike/tameike-sar-water-area/pond_dates.csv (every pond and scene), outputs/pairs.csv (S1 and S2 within 2 days),
outputs/b1.csv, outputs/b2.csv and outputs/robustness.csv.
"""

import csv
import json
import os
from pathlib import Path

import numpy as np
import rasterio

from scipy import ndimage

from build_masks import ART, BOXES, OUT as OUT_MAIN
from water_stats import best_shift, pair_dates, pond_fractions, shifted, twoway_resid

CLASSES = ["0.1-0.5ha", "0.5-1ha", "1-5ha", ">=5ha"]
CLOUD = {0, 1, 3, 8, 9, 10}           # no data, saturated, cloud shadow, cloud medium, cloud high, cirrus
S1_THR = {"main": -15.0, "s1_-13": -13.0, "s1_-17": -17.0}
S2_THR = {"main": 0.0, "s2_0.1": 0.1, "s2_-0.1": -0.1}
MIN_PIX = 4
MIN_CLEAR = 0.9
N_BOOT, N_PERM = 1000, 200
# exploratory (decided after the first run, see EXPERIMENT_TRACKER.md R002): measure the shifts only on pixels within
# 100 m of a pond outline, so the sea and other large water bodies do not decide the shift
SHIFT_NEAR_PONDS = os.environ.get("SHIFT_NEAR_PONDS") == "1"
OUT = OUT_MAIN / "explore_shift_near_ponds" if SHIFT_NEAR_PONDS else OUT_MAIN
PONDS_CSV_DIR = OUT_MAIN


def load_scenes(key):
    d = ART / "scenes" / key
    s1 = {p.stem[3:]: p for p in sorted(d.glob("S1_*.npz"))}
    s2 = {p.stem[3:]: p for p in sorted(d.glob("S2_*.npz"))}
    return s1, s2


def s1_db(path):
    vv = np.load(path)["vv"].astype("float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(vv > 0, 10 * np.log10(vv), np.nan)


def s2_arrays(path):
    z = np.load(path)
    off = 1000.0 if str(z["baseline"]) >= "04.00" else 0.0
    g = z["b03"].astype("float64")
    n = z["b08"].astype("float64")
    has = (z["b03"] > 0) & (z["b08"] > 0)
    gr, nr = (g - off) / 1e4, (n - off) / 1e4
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = np.where(has, (gr - nr) / (gr + nr), np.nan)
    return ndwi, z["scl"], has


def box_records(key):
    with rasterio.open(ART / f"{key}_inner10.tif") as d:
        inner = d.read(1)
    with rasterio.open(ART / f"{key}_ponds10.tif") as d:
        full = d.read(1)
    ponds = {int(r["pond"]): r for r in csv.DictReader(open(PONDS_CSV_DIR / f"{key}_ponds.csv", encoding="utf-8"))}
    ids = [p for p, r in ponds.items() if r["size_class"] in CLASSES]
    s1, s2 = load_scenes(key)

    # B0: shifts against the pond outlines
    stack = np.stack([s1_db(p) for p in s1.values()])
    s1_med = np.nanmedian(stack, axis=0)
    del stack
    nd = []
    for p in s2.values():
        ndwi, scl, has = s2_arrays(p)
        nd.append(np.where(has & ~np.isin(scl, list(CLOUD)), ndwi, np.nan))
    with np.errstate(all="ignore"):
        s2_med = np.nanmedian(np.stack(nd), axis=0)
    del nd
    mask = full > 0
    near = ndimage.binary_dilation(mask, iterations=10) if SHIFT_NEAR_PONDS else None
    sh1, c1 = best_shift(mask, -np.nan_to_num(s1_med, nan=np.nanmean(s1_med)), where=near)
    sh2, c2 = best_shift(mask, np.nan_to_num(s2_med, nan=np.nanmean(s2_med)), where=near)
    b0 = dict(box=key, s1_scenes=len(s1), s2_dates=len(s2), s1_shift_rows_cols=sh1, s1_shift_corr=round(c1, 3),
              s2_shift_rows_cols=sh2, s2_shift_corr=round(c2, 3))
    _, c1_0 = best_shift(mask, -np.nan_to_num(s1_med, nan=np.nanmean(s1_med)), r=0, where=near)
    _, c2_0 = best_shift(mask, np.nan_to_num(s2_med, nan=np.nanmean(s2_med)), r=0, where=near)
    b0.update(s1_corr_unshifted=round(c1_0, 3), s2_corr_unshifted=round(c2_0, 3))

    rows = []
    for outline, lab in (("inner", inner), ("full", full)):
        for d, p in s1.items():
            db = shifted(s1_db(p), sh1)
            valid = np.isfinite(db)
            for var, thr in S1_THR.items():
                if outline == "full" and var != "main":
                    continue
                n, f = pond_fractions(lab, valid, db < thr, ids)
                for pid, nn, ff in zip(ids, n, f):
                    rows.append(dict(box=key, pond=pid, size_class=ponds[pid]["size_class"], outline=outline,
                                     sensor="S1", date=d, variant=var, n_valid=int(nn), clear_share="",
                                     frac=None if np.isnan(ff) else round(float(ff), 4)))
        for d, p in s2.items():
            ndwi, scl, has = s2_arrays(p)
            ndwi, has = shifted(ndwi, sh2), shifted(has.astype(float), sh2) == 1
            scl = shifted(scl.astype(float), sh2)
            clear = has & ~np.isin(np.nan_to_num(scl, nan=0).astype(int), list(CLOUD))
            n_has, _ = pond_fractions(lab, has, has, ids)
            variants = {k: ndwi > t for k, t in S2_THR.items()}
            variants["s2_scl_water"] = scl == 6
            for var, wat in variants.items():
                if outline == "full" and var != "main":
                    continue
                n, f = pond_fractions(lab, clear, wat, ids)
                for pid, nn, nh, ff in zip(ids, n, n_has, f):
                    rows.append(dict(box=key, pond=pid, size_class=ponds[pid]["size_class"], outline=outline,
                                     sensor="S2", date=d, variant=var, n_valid=int(nn),
                                     clear_share=round(float(nn / nh), 3) if nh else 0.0,
                                     frac=None if np.isnan(ff) else round(float(ff), 4)))
    return b0, rows, list(s1), list(s2)


def boot_ci(values_by_pond, stat, rng):
    keys = list(values_by_pond)
    out = []
    for _ in range(N_BOOT):
        pick = rng.choice(len(keys), len(keys), replace=True)
        out.append(stat([values_by_pond[keys[i]] for i in pick]))
    return [round(float(np.nanpercentile(out, 2.5)), 4), round(float(np.nanpercentile(out, 97.5)), 4)]


def make_pairs(rows, pairing, s1_var="main", s2_var="main", outline="inner"):
    s1 = {(r["box"], r["pond"], r["date"]): r for r in rows
          if r["sensor"] == "S1" and r["variant"] == s1_var and r["outline"] == outline}
    s2 = {(r["box"], r["pond"], r["date"]): r for r in rows
          if r["sensor"] == "S2" and r["variant"] == s2_var and r["outline"] == outline}
    out = []
    for (box, pond, d1), a in s1.items():
        d2 = pairing[box].get(d1)
        if d2 is None:
            continue
        b = s2.get((box, pond, d2))
        if b is None or a["frac"] is None or b["frac"] is None:
            continue
        if a["n_valid"] < MIN_PIX or b["n_valid"] < MIN_PIX or b["clear_share"] < MIN_CLEAR:
            continue
        out.append(dict(box=box, pond=pond, size_class=a["size_class"], s1_date=d1, s2_date=d2,
                        s1_frac=a["frac"], s2_frac=b["frac"], n_s1=a["n_valid"], n_s2=b["n_valid"]))
    return out


def b1_b2(pairs, rng_seed=0):
    by = {}
    for p in pairs:
        by.setdefault(p["size_class"], []).append(p)
    # B2 residuals on all ponds with >= 3 pairs, pond and box-date effects together
    count = {}
    for p in pairs:
        count[(p["box"], p["pond"])] = count.get((p["box"], p["pond"]), 0) + 1
    use = [p for p in pairs if count[(p["box"], p["pond"])] >= 3]
    pond_key = np.array([f"{p['box']}:{p['pond']}" for p in use])
    date_key = np.array([f"{p['box']}:{p['s1_date']}" for p in use])
    x1 = np.array([p["s1_frac"] for p in use])
    x2 = np.array([p["s2_frac"] for p in use])
    r1, r2 = twoway_resid(x1, pond_key, date_key), twoway_resid(x2, pond_key, date_key)
    pond_only = lambda x: x - (np.bincount(np.unique(pond_key, return_inverse=True)[1], weights=x)
                              / np.bincount(np.unique(pond_key, return_inverse=True)[1]))[np.unique(pond_key, return_inverse=True)[1]]
    q1, q2 = pond_only(x1), pond_only(x2)
    cls = np.array([p["size_class"] for p in use])

    rng = np.random.default_rng(rng_seed)
    perm = {c: [] for c in CLASSES}
    inv = np.unique(pond_key, return_inverse=True)[1]
    for _ in range(N_PERM):
        x1p = x1.copy()
        for g in np.unique(inv):
            idx = np.flatnonzero(inv == g)
            x1p[idx] = x1p[rng.permutation(idx)]
        r1p = twoway_resid(x1p, pond_key, date_key)
        for c in CLASSES:
            m = cls == c
            if m.sum() > 2 and np.std(r1p[m]) > 0 and np.std(r2[m]) > 0:
                perm[c].append(np.corrcoef(r1p[m], r2[m])[0, 1])

    b1, b2 = [], []
    rng = np.random.default_rng(rng_seed)
    for c in CLASSES:
        ps = by.get(c, [])
        if not ps:
            b1.append(dict(size_class=c, ponds=0, pairs=0))
            b2.append(dict(size_class=c, ponds=0, pairs=0))
            continue
        diffs = {}
        for p in ps:
            diffs.setdefault((p["box"], p["pond"]), []).append(abs(p["s1_frac"] - p["s2_frac"]))
        med = float(np.median([d for v in diffs.values() for d in v]))
        ci = boot_ci(diffs, lambda vs: np.median([d for v in vs for d in v]), rng)
        b1.append(dict(size_class=c, ponds=len(diffs), pairs=len(ps), median_abs_diff=round(med, 4),
                       ci_low=ci[0], ci_high=ci[1],
                       median_s1_frac=round(float(np.median([p["s1_frac"] for p in ps])), 4),
                       median_s2_frac=round(float(np.median([p["s2_frac"] for p in ps])), 4)))
        m = cls == c
        if m.sum() > 2 and np.std(r1[m]) > 0 and np.std(r2[m]) > 0:
            groups = {}
            for i in np.flatnonzero(m):
                groups.setdefault(pond_key[i], []).append(i)
            corr = lambda vs: (np.corrcoef(r1[np.concatenate(vs)], r2[np.concatenate(vs)])[0, 1]
                               if np.std(r1[np.concatenate(vs)]) > 0 and np.std(r2[np.concatenate(vs)]) > 0 else np.nan)
            cc = float(np.corrcoef(r1[m], r2[m])[0, 1])
            ci2 = boot_ci(groups, lambda vs: corr(vs), rng)
            pc = perm[c]
            b2.append(dict(size_class=c, ponds=len(groups), pairs=int(m.sum()), corr_twoway=round(cc, 4),
                           ci_low=ci2[0], ci_high=ci2[1],
                           corr_pond_only=round(float(np.corrcoef(q1[m], q2[m])[0, 1]), 4),
                           perm_mean=round(float(np.mean(pc)), 4) if pc else None,
                           perm_p975=round(float(np.percentile(pc, 97.5)), 4) if pc else None,
                           perm_share_ge=round(float(np.mean(np.array(pc) >= cc)), 4) if pc else None))
        else:
            b2.append(dict(size_class=c, ponds=0, pairs=int(m.sum())))
    return b1, b2


def write_csv(path, rows):
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True)
    b0s, rows, pairing = [], [], {}
    for key in BOXES:
        b0, r, s1d, s2d = box_records(key)
        b0s.append(b0)
        rows += r
        pairing[key] = pair_dates(s1d, s2d, 2)
        b0["pairs_of_dates"] = len(pairing[key])
        print(b0, flush=True)
    # C0: ponds >= 5 ha, inner outline, main thresholds, every valid pond-date of each sensor
    big1 = [r["frac"] for r in rows if r["size_class"] == ">=5ha" and r["outline"] == "inner" and r["variant"] == "main"
            and r["sensor"] == "S1" and r["frac"] is not None and r["n_valid"] >= MIN_PIX]
    big2 = [r["frac"] for r in rows if r["size_class"] == ">=5ha" and r["outline"] == "inner" and r["variant"] == "main"
            and r["sensor"] == "S2" and r["frac"] is not None and r["n_valid"] >= MIN_PIX and r["clear_share"] >= MIN_CLEAR]
    c0 = dict(s1_median_frac_ge5ha=round(float(np.median(big1)), 4), s1_n=len(big1),
              s2_median_frac_ge5ha=round(float(np.median(big2)), 4), s2_n=len(big2))
    c0["pass"] = c0["s1_median_frac_ge5ha"] >= 0.8 and c0["s2_median_frac_ge5ha"] >= 0.8
    (OUT / "b0.json").write_text(json.dumps(dict(boxes=b0s, c0=c0), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(c0, flush=True)
    art = ART / OUT.relative_to(OUT_MAIN) if OUT != OUT_MAIN else ART
    art.mkdir(parents=True, exist_ok=True)
    write_csv(art / "pond_dates.csv", rows)  # every pond and scene, 26 MB: kept out of git

    pairs = make_pairs(rows, pairing)
    write_csv(OUT / "pairs.csv", pairs)
    b1, b2 = b1_b2(pairs)
    write_csv(OUT / "b1.csv", b1)
    write_csv(OUT / "b2.csv", b2)
    for r in b1 + b2:
        print(r, flush=True)

    rob = []
    for name, kw in [("s1_-13", dict(s1_var="s1_-13")), ("s1_-17", dict(s1_var="s1_-17")),
                     ("s2_0.1", dict(s2_var="s2_0.1")), ("s2_-0.1", dict(s2_var="s2_-0.1")),
                     ("s2_scl_water", dict(s2_var="s2_scl_water")), ("full_outline", dict(outline="full"))]:
        pr = make_pairs(rows, pairing, **kw)
        v1, v2 = b1_b2(pr)
        for a, b in zip(v1, v2):
            rob.append(dict(variant=name, size_class=a["size_class"], pairs=a.get("pairs"),
                            median_abs_diff=a.get("median_abs_diff"), corr_twoway=b.get("corr_twoway"),
                            corr_ci_low=b.get("ci_low"), corr_ci_high=b.get("ci_high")))
    write_csv(OUT / "robustness.csv", rob)


if __name__ == "__main__":
    main()
