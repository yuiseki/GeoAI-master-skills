"""Run the change test on both orbits and judge B0-B4 of EXPERIMENT_PLAN.md, with the robustness variants.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy python scripts/04_blocks.py

Reads artifacts/_flood/kita-inbanuma-sar-changepoint/{stack_o39,stack_o141}.npy, aux.npz and outputs/quality.json.
Writes outputs/blocks.json (every block, main and variants), outputs/daily_o39.csv and outputs/daily_o141.csv (per date
and pixel set, the share of pixels with a darkening or a brightening change, main analysis) and
artifacts/.../change_o39.npz, change_o141.npz (main analysis: change, ratio_db as float16) for the figures.
"""
import csv
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from cp import log_ratio, sequential

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/kita-inbanuma-sar-changepoint"
OUT = HERE.parent / "outputs"
ALPHA = 0.01
PRE = {39: "2026-09-12", 141: "2026-09-07"}  # last date before the event in each orbit
CHUNK = 170


def enl_rule():
    q = json.loads((OUT / "quality.json").read_text(encoding="utf-8"))
    v = [r[f"enl_ratio_{p}"] for o in q["orbits"].values() for r in o for p in ("vv", "vh") if f"enl_ratio_{p}" in r]
    return round(float(np.median(v)), 1), len(v)


def pixel_sets(aux):
    wc, dem = aux["wc"], aux["dem"]
    outlines = aux["ref_0922"] | aux["ref_0924"] | aux["ref_0925"] | aux["ref_1001"]
    far = ndimage.distance_transform_edt(~outlines) * 10 >= 300
    land = (wc != 80) & np.isfinite(dem)
    edge = ndimage.maximum_filter(wc, size=5) != ndimage.minimum_filter(wc, size=5)
    return {"IN39": aux["ref_0924"] & land, "IN141": aux["ref_1001"] & land,
            "RECEDED": aux["ref_0924"] & ~aux["ref_1001"] & land,
            "CTRL": np.isin(wc, [30, 40]) & (dem < 10) & far & land,
            "STABLE": (wc == 10) & (dem >= 15) & far & land}, edge


def run(stack, L, alpha, pols):
    """Sequential test in row chunks. Returns change (ndate, rows, cols) and ratio_db (float16)."""
    _, nd, H, W = stack.shape
    change = np.zeros((nd, H, W), bool)
    ratio = np.zeros((nd, H, W), np.float16)
    for r0 in range(0, H, CHUNK):
        sub = np.asarray(stack[list(pols), :, r0:r0 + CHUNK], float)
        o = sequential(sub, L, alpha)
        change[:, r0:r0 + CHUNK] = o["change"]
        ratio[:, r0:r0 + CHUNK] = np.nan_to_num(o["ratio_db"]).astype(np.float16)
    return change, ratio


def sim_false_alarm(nd, L, alpha, npol, n=200_000, seed=7):
    rng = np.random.default_rng(seed)
    x = rng.gamma(L, 1 / L, size=(npol, nd, n))
    return float(sequential(x, L, alpha)["change"][1:].mean())


def share(mask, sel):
    n = int(sel.sum())
    return {"n": n, "k": int((mask & sel).sum()), "share": round(float((mask & sel).sum() / n), 4) if n else None}


def judge(o, dates, change, ratio, sets, L, alpha, npol, keep=None):
    keep = np.ones(change.shape[1:], bool) if keep is None else keep
    S = {k: v & keep for k, v in sets.items()}
    di = {d: i for i, d in enumerate(dates)}
    dark, bright = change & (ratio < 0), change & (ratio > 0)
    pre = [i for i, d in enumerate(dates) if 0 < i and d <= PRE[o]]
    stable_rates = [float(change[i][S["STABLE"]].mean()) for i in pre]
    fa = sim_false_alarm(len(pre) + 1, L, alpha, npol)
    res = {"B0": {"stable_pre_mean": round(float(np.mean(stable_rates)), 5), "sim_false_alarm": round(fa, 5),
                  "ratio": round(float(np.mean(stable_rates)) / fa, 3),
                  "stable_pre_by_date": dict(zip([dates[i] for i in pre], [round(r, 5) for r in stable_rates]))}}
    res["B0"]["supported"] = res["B0"]["ratio"] <= 2
    if o == 39:
        t = di["2026-09-24"]
        pin, pc = share(dark[t], S["IN39"]), share(dark[t], S["CTRL"])
        res["B1"] = {"in": pin, "ctrl": pc, "supported": bool(pin["share"] >= 0.5 and pin["share"] >= 3 * pc["share"])}
        if "2026-10-18" in di:
            u = di["2026-10-18"]
            rec = S["RECEDED"] & dark[t]
            ctl = S["CTRL"] & dark[t]
            res["B3"] = {"receded_dark_0924": share(bright[u], rec), "ctrl_dark_0924": share(bright[u], ctl)}
            res["B3"]["supported"] = bool(res["B3"]["receded_dark_0924"]["share"] >= 0.5)
    else:
        a, b = di["2026-09-19"], di["2026-10-01"]
        either = dark[a] | dark[b]
        pin, pc = share(either, S["IN141"]), share(either, S["CTRL"])
        res["B2"] = {"in": pin, "ctrl": pc, "in_0919": share(dark[a], S["IN141"]), "in_1001": share(dark[b], S["IN141"]),
                     "ctrl_0919": share(dark[a], S["CTRL"]), "ctrl_1001": share(dark[b], S["CTRL"]),
                     "supported": bool(pin["share"] >= 0.5 and pin["share"] >= 3 * pc["share"])}
    return res


def baseline_b4(stack, dates, change, sets, pols):
    """B4: the two-date difference at the omnibus false alarm rate on STABLE before the event (and on CTRL, reference)."""
    di = {d: i for i, d in enumerate(dates)}
    t = di["2026-09-24"]
    pre = [i for i, d in enumerate(dates) if 0 < i and d <= PRE[39]]
    db = 10 * np.log10(np.asarray(stack[list(pols)], float))

    def diff_at(sel):
        x = db[:, :, sel]  # npol x ndate x npix
        prev = np.full(x.shape[::2], np.nan)
        out = np.full(x.shape[1:], np.nan)
        for i in range(x.shape[1]):
            ok = np.all(np.isfinite(x[:, i]), axis=0)
            has = ok & np.all(np.isfinite(prev), axis=0)
            out[i] = np.where(has, np.abs(x[:, i] - prev).max(axis=0), np.nan)
            prev = np.where(ok, x[:, i], prev)
        return out

    res = {}
    for match in ("STABLE", "CTRL"):
        target = float(np.mean([change[i][sets[match]].mean() for i in pre]))
        d = diff_at(sets[match])[pre]
        grid = np.round(np.arange(0, 20, 0.01), 2)
        rates = np.array([np.mean(np.nan_to_num(d, nan=-1) >= g) for g in grid])
        thr = float(grid[np.argmax(rates <= target)])
        base = log_ratio(db[:, :, sets["IN39"]], thr)[t]
        omni = change[t][sets["IN39"]]
        res[f"match_{match}"] = {"target_rate": round(target, 5), "threshold_db": thr,
                                 "baseline_rate_at_threshold": round(float(rates[np.argmax(rates <= target)]), 5),
                                 "omnibus_in39": round(float(omni.mean()), 4), "baseline_in39": round(float(base.mean()), 4),
                                 "difference": round(float(omni.mean() - base.mean()), 4)}
    res["supported"] = bool(res["match_STABLE"]["difference"] >= 0.05)
    return res


def daily(o, dates, change, ratio, sets):
    rows = []
    for i, d in enumerate(dates):
        for name in ("IN39", "IN141", "RECEDED", "CTRL", "STABLE"):
            s = sets[name]
            rows.append({"orbit": o, "date": d, "set": name, "pixels": int(s.sum()),
                         "dark": round(float((change[i] & (ratio[i] < 0))[s].mean()), 5),
                         "bright": round(float((change[i] & (ratio[i] > 0))[s].mean()), 5)})
    with open(OUT / f"daily_o{o}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    aux = np.load(ART / "aux.npz")
    sets, edge = pixel_sets(aux)
    L, n_enl = enl_rule()
    out = {"enl": L, "enl_values": n_enl, "alpha": ALPHA,
           "sets": {k: int(v.sum()) for k, v in sets.items()}, "edge_pixels": int(edge.sum()), "orbits": {}}
    print("ENL", L, "sets", out["sets"])
    for o in (39, 141):
        stack = np.load(ART / f"stack_o{o}.npy", mmap_mode="r")
        dates = [str(d) for d in aux[f"dates_o{o}"]]
        miss = {k: int((~np.all(np.isfinite(np.asarray(stack[:, :, v])), axis=(0, 1))).sum()) for k, v in sets.items()}
        change, ratio = run(stack, L, ALPHA, (0, 1))
        np.savez_compressed(ART / f"change_o{o}.npz", change=change, ratio_db=ratio, dates=np.array(dates))
        daily(o, dates, change, ratio, sets)
        res = {"dates": dates, "pixels_with_a_missing_date": miss,
               "main": judge(o, dates, change, ratio, sets, L, ALPHA, 2)}
        if o == 39:
            res["main"]["B4"] = baseline_b4(stack, dates, change, sets, (0, 1))
        res["main"]["edge_excluded"] = judge(o, dates, change, ratio, sets, L, ALPHA, 2, keep=~edge)
        variants = {}
        for name, (LL, a, pols, start) in {"alpha_0.001": (L, 0.001, (0, 1), None), "alpha_0.05": (L, 0.05, (0, 1), None),
                                           "enl_x0.75": (round(L * 0.75, 2), ALPHA, (0, 1), None),
                                           "enl_x1.25": (round(L * 1.25, 2), ALPHA, (0, 1), None),
                                           "vv_only": (L, ALPHA, (0,), None),
                                           "from_july": (L, ALPHA, (0, 1), "2026-07-01")}.items():
            idx = [i for i, d in enumerate(dates) if start is None or d >= start]
            st = stack[:, idx] if start else stack
            dd = [dates[i] for i in idx]
            c, r = run(st, LL, a, pols)
            variants[name] = judge(o, dd, c, r, sets, LL, a, len(pols))
            print(o, name, {k: v.get("supported") for k, v in variants[name].items()})
        res["variants"] = variants
        out["orbits"][o] = res
        print(o, "main", json.dumps({k: v for k, v in res["main"].items() if k != "edge_excluded"}, ensure_ascii=False)[:1500])
    (OUT / "blocks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
