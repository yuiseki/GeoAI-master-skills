"""Blocks B0 to B3 of EXPERIMENT_PLAN.md, the descriptive quantities, the robustness table and orbit 39.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with scikit-image --with pyproj python -u scripts/03_blocks.py

Reads stack_o46.npy, stack_o39.npy, aux.npz (02_grid.py) and outputs/grid_summary.json. Writes
- outputs/blocks.json: main settings (orbit 46, 10-13 05:43): every observable with its 90 % interval and the decision
  of each claim; the descriptive quantities; the robustness variants; the same quantities for orbit 39 (10-12 17:41)
- outputs/rec_by_municipality.csv: per municipality, REC pixels, dark and bright shares, land cover mix
- outputs/groups_landcover.csv: the WorldCover mix of each group
- artifacts/.../delta_o46.npz, delta_o39.npz: dVV, dVH (dB, main settings) and the after-scene dVV, for the figures
"""
import csv
import json

import numpy as np

import flood
from common import ART, OUT, SCENES

THR, K, CH_W, REC_GAP, BLOCK, NBOOT, MIN_N = 3.0, 3, 300.0, 300.0, 1000.0, 2000, 1000
WC_NAMES = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare", 80: "water", 90: "wetland",
            95: "mangrove", 100: "moss"}


def load(o, shift):
    st = np.load(ART / f"stack_o{o}.npy", mmap_mode="r")
    roles = [r for r, _ in SCENES[o]]
    pre = [i for i, r in enumerate(roles) if r == "pre"]
    ev, af = roles.index("event"), roles.index("after")
    out = {}
    for k, pol in enumerate(("vv", "vh")):
        sel = {"pre_all": np.nanmean(np.asarray(st[k, pre], float), axis=0), "pre_last": np.asarray(st[k, pre[-1]], float),
               "event": np.asarray(st[k, ev], float), "after": np.asarray(st[k, af], float)}
        out[pol] = {n: flood.apply_int_shift(a, shift) if any(shift) else a for n, a in sel.items()}
    return out


def deltas(img, k, pre):
    d = {}
    for pol in ("vv", "vh"):
        p = flood.boxcar(img[pol][pre], k)
        d[pol] = flood.ratio_db(flood.boxcar(img[pol]["event"], k), p)
        d[pol + "_after"] = flood.ratio_db(flood.boxcar(img[pol]["after"], k), p)
    return d


def groups(aux, valid, ch_w=CH_W, ctrl_any=False):
    a31a, rec = aux["a31a"], aux["rec"] & valid
    ch = (aux["dist_tama"] <= ch_w) & ~a31a & ~aux["rec"] & valid
    a = a31a & ~aux["rec"] & ~ch & valid
    if ctrl_any:
        ctrl = ~ch & (aux["dist_rec"] >= REC_GAP) & valid & ~((aux["dist_tama"] <= CH_W) & ~a31a)
    else:
        ctrl = ~a31a & ~ch & (aux["dist_rec"] >= REC_GAP) & valid & ~((aux["dist_tama"] <= CH_W) & ~a31a)
    return {"REC": rec, "CHANNEL": ch, "A31A": a, "CTRL": ctrl}


def std_compare(flag, wc, tgt, ref, units_t, units_r, rng):
    """Rate in tgt, the rate of ref standardised to tgt's class mix, their ratio, with bootstrap intervals."""
    s = flood.standardized_rate(flag, wc, tgt, ref, MIN_N)
    keep = np.isin(wc, s["classes"])
    t = tgt & keep
    p_t = float(flag[t].mean())
    cl, cn = np.unique(wc[t], return_counts=True)
    w = {int(c): n / cn.sum() for c, n in zip(cl, cn)}
    dt = flood.rate_draws(flag[t], units_t[t], NBOOT, rng)
    dr = flood.std_rate_draws(flag[ref], wc[ref], units_r[ref], w, NBOOT, rng)
    q = lambda v: [round(float(np.nanquantile(v, 0.05)), 4), round(float(np.nanquantile(v, 0.95)), 4)]
    return {"p_target": round(p_t, 4), "p_target_ci": q(dt), "p_ref_std": round(s["rate"], 4), "p_ref_std_ci": q(dr),
            "ratio": round(p_t / s["rate"], 3) if s["rate"] > 0 else None, "ratio_ci": q(dt / dr),
            "target_pixels": int(t.sum()), "dropped_share": round(s["dropped_share"], 4),
            "dropped_classes": s["dropped_classes"], "ref_class_rates": {WC_NAMES[c]: round(r, 4) for c, r in
                                                                          s["class_rates"].items()}}


def evaluate(aux, d, valid_extra=None, ch_w=CH_W, ctrl_any=False, pol="vv", thr=THR, corr=False, seed=0):
    rng = np.random.default_rng(seed)
    wc = aux["wc"]
    dv = d["vv"] if pol == "vv" else d["vh"]
    valid = aux["tokyo"] & (wc != 80) & np.isfinite(d["vv"]) & np.isfinite(d["vh"])
    if valid_extra is not None:
        valid &= valid_extra
    g = groups(aux, valid, ch_w, ctrl_any)
    med = {p: float(np.median(d[p][g["CTRL"]])) for p in ("vv", "vh")}
    if pol == "either":
        a, b = d["vv"] - (med["vv"] if corr else 0), d["vh"] - (med["vh"] if corr else 0)
        dark, bright = (a <= -thr) | (b <= -thr), (a >= thr) | (b >= thr)
    else:
        x = dv - (med[pol] if corr else 0)
        dark, bright = x <= -thr, x >= thr
    comp = flood.components(g["REC"])
    blocks = flood.block_ids(aux["x"], aux["y"], BLOCK)
    out = {"ctrl_median_db": {p: round(v, 3) for p, v in med.items()},
           "pixels": {n: int(m.sum()) for n, m in g.items()}, "rec_components": int(comp.max())}
    out["B0"] = std_compare(dark, wc, g["CHANNEL"], g["CTRL"], blocks, blocks, rng)
    out["B1"] = std_compare(dark, wc, g["REC"], g["CTRL"], comp, blocks, rng)
    b50 = wc == 50
    out["B2"] = std_compare(bright, wc, g["REC"] & b50, g["CTRL"] & b50, comp, blocks, rng)
    pop = valid & ~g["CHANNEL"] & ~g["REC"] & ~((aux["dist_tama"] <= CH_W) & ~aux["a31a"])
    in_a = g["A31A"]
    ld = flood.lift_draws(dark[pop], in_a[pop], blocks[pop], NBOOT, rng)
    out["B3"] = {"lift": round(flood.lift(dark, in_a, pop), 3),
                 "lift_ci": [round(float(np.nanquantile(ld, 0.05)), 3), round(float(np.nanquantile(ld, 0.95)), 3)],
                 "pop_pixels": int(pop.sum()), "a31a_share_of_pop": round(float(in_a[pop].mean()), 4),
                 "a31a_share_of_dark": round(float(in_a[dark & pop].mean()), 4), "dark_pixels": int((dark & pop).sum()),
                 "lift_by_landcover": {WC_NAMES[c]: round(flood.lift(dark, in_a, pop & (wc == c)), 3)
                                       for c in np.unique(wc[pop]) if (pop & (wc == c) & in_a).sum() >= MIN_N
                                       and (pop & (wc == c) & ~in_a).sum() >= MIN_N}}
    out["bright_also"] = {n: round(float(bright[m].mean()), 4) for n, m in g.items()}
    out["dark_also"] = {n: round(float(dark[m].mean()), 4) for n, m in g.items()}
    return out, g, dark, bright


def decide(m):
    b0, b1, b2, b3 = m["B0"], m["B1"], m["B2"], m["B3"]
    return {"C0": "supported" if b0["p_target"] >= 0.3 and b0["p_target"] >= 3 * b0["p_ref_std"] else "rejected",
            "C1": "supported" if b1["p_target"] >= 2 * b1["p_ref_std"] else "rejected",
            "C2": "supported" if b1["p_target"] >= 0.5 else "rejected",
            "C3": "supported" if b2["p_target"] >= 2 * b2["p_ref_std"] else "rejected",
            "C4": "supported" if b3["lift"] >= 2 else "rejected"}


def main():
    aux = dict(np.load(ART / "aux.npz"))
    t = aux["transform"]
    rr, cc = np.mgrid[0:aux["wc"].shape[0], 0:aux["wc"].shape[1]]
    aux["x"], aux["y"] = t[2] + (cc + 0.5) * t[0], t[5] + (rr + 0.5) * t[4]
    gsum = json.loads((OUT / "grid_summary.json").read_text(encoding="utf-8"))
    res = {"settings": {"thr_db": THR, "boxcar": K, "channel_width_m": CH_W, "rec_gap_m": REC_GAP, "block_m": BLOCK,
                        "nboot": NBOOT, "min_class_pixels": MIN_N}}
    for o in (46, 39):
        shift = gsum["orbits"][str(o)]["shift_back"]
        img = load(o, shift)
        d = deltas(img, K, "pre_all")
        m, g, dark, bright = evaluate(aux, d)
        m["shift_back"] = shift
        m["decisions"] = decide(m)
        # descriptive
        rec = g["REC"]
        m["rec_share_in_a31a"] = round(float(aux["a31a"][rec].mean()), 4)
        m["rec_share_in_a31a_all_rec_pixels"] = round(float(aux["a31a"][aux["rec"] & aux["tokyo"]].mean()), 4)
        valid_af = np.isfinite(d["vv_after"])
        m["recovered_by_after"] = {n: {"dark_pixels": int((dark & g[n] & valid_af).sum()),
                                       "share_back": round(float((d["vv_after"] > -1.5)[dark & g[n] & valid_af].mean()), 4)
                                       if (dark & g[n] & valid_af).sum() else None} for n in g}
        m["after_scene"] = [s for s in gsum["orbits"][str(o)]["scenes"] if s["role"] == "after"][0]["date"]
        res[f"o{o}"] = m
        np.savez_compressed(ART / f"delta_o{o}.npz", dvv=d["vv"].astype(np.float32), dvh=d["vh"].astype(np.float32),
                            dvv_after=d["vv_after"].astype(np.float32))
        if o == 46:
            with open(OUT / "rec_by_municipality.csv", "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ward_code", "rec_pixels", "dark_share", "bright_share", "built_share", "tree_share",
                            "grass_share", "crop_share", "in_a31a_share"])
                for code in np.unique(aux["ward"][rec]):
                    mm = rec & (aux["ward"] == code)
                    w.writerow([int(code), int(mm.sum()), round(float(dark[mm].mean()), 4),
                                round(float(bright[mm].mean()), 4)] +
                               [round(float((aux["wc"][mm] == c).mean()), 4) for c in (50, 10, 30, 40)] +
                               [round(float(aux["a31a"][mm].mean()), 4)])
            with open(OUT / "groups_landcover.csv", "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["group", "pixels"] + [WC_NAMES[c] for c in (10, 30, 40, 50, 60, 90)])
                for n, mm in g.items():
                    w.writerow([n, int(mm.sum())] + [round(float((aux["wc"][mm] == c).mean()), 4)
                                                     for c in (10, 30, 40, 50, 60, 90)])
            # robustness, orbit 46 only
            var = {}
            for name, kw, kk, pre, sh in (
                    ("thr_2", {"thr": 2.0}, K, "pre_all", shift), ("thr_4", {"thr": 4.0}, K, "pre_all", shift),
                    ("boxcar_1", {}, 1, "pre_all", shift), ("boxcar_5", {}, 5, "pre_all", shift),
                    ("pol_vh", {"pol": "vh"}, K, "pre_all", shift), ("pol_either", {"pol": "either"}, K, "pre_all", shift),
                    ("platform_corrected", {"corr": True}, K, "pre_all", shift),
                    ("channel_200", {"ch_w": 200.0}, K, "pre_all", shift),
                    ("channel_400", {"ch_w": 400.0}, K, "pre_all", shift),
                    ("ctrl_any_a31a", {"ctrl_any": True}, K, "pre_all", shift),
                    ("pre_last_only", {}, K, "pre_last", shift),
                    ("shift_other_way", {}, K, "pre_all", [0, 0] if any(shift) else
                     [int(round(v)) for v in gsum["orbits"]["46"]["pre_vs_water_shift_rows_cols"]])):
                im = img if sh == shift else load(o, sh)
                vm = evaluate(aux, deltas(im, kk, pre), **kw)[0]
                vm["decisions"] = decide(vm)
                var[name] = {k: vm[k] for k in ("B0", "B1", "B2", "B3", "decisions", "ctrl_median_db", "pixels")}
                print("variant", name, vm["decisions"], flush=True)
            res["o46_variants"] = var
        print(o, json.dumps({k: m[k] for k in ("decisions", "ctrl_median_db", "pixels")}, ensure_ascii=False), flush=True)
    (OUT / "blocks.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    m = res["o46"]
    print(json.dumps({k: m[k] for k in ("B0", "B1", "B2", "B3", "decisions", "rec_share_in_a31a", "recovered_by_after")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
