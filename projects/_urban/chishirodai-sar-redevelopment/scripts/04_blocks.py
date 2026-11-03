"""Blocks A1, A2, B1, B2 of EXPERIMENT_PLAN.md and the robustness table.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with pyproj python -u scripts/04_blocks.py

Reads stack.npy and aux.npz (02_grid.py), labels/labels.csv and outputs/s2_break.json (03_s2.py). Writes
- outputs/blocks.json: every observable, the decision of each claim, and the robustness variants
- outputs/tiles.csv: per labelled tile, the label, the SAR score (main and variants), the built-up share, the ranks
- outputs/site_series.csv: per date, the mean dB (VV, VH) of SITE and CTRL, and the share of SITE and CTRL pixels with a
  darkening change point at that date (main settings)
- artifacts/.../change_site_ctrl.npz: change points of SITE and CTRL pixels (main settings)
"""
import csv
import datetime as dt
import json

import numpy as np

import cp
from common import ART, HERE, OUT
from rank import hypergeom_tail, rank_order, recall_at

W = ("2019-04-01", "2025-03-31")
FY2019 = ("2019-04-01", "2020-03-31")
FY2024 = ("2024-04-01", "2025-03-31")
ALPHA, ENL = 0.001, 4.4
SITE_TILE = "58289_25820"


def ordinal(d):
    return dt.date.fromisoformat(d).toordinal()


def run_seq(stack, mask, L, alpha, pols=(0, 1)):
    x = np.asarray(stack[list(pols)][:, :, mask], float)
    cp._NULL.clear()
    return cp.sequential(x, L, alpha)


def a_observables(res, dates, is_site):
    inw = np.array([W[0] <= d <= W[1] for d in dates])
    dark = res["change"] & (res["ratio_db"] < 0)
    has = dark[inw].any(0)
    p_site, p_ctrl = float(has[is_site].mean()), float(has[~is_site].mean())
    r = np.where(dark & inw[:, None], res["ratio_db"], np.inf)
    idx = r.argmin(0)
    ok = is_site & has
    days = np.array([ordinal(dates[i]) for i in idx[ok]])
    med = dt.date.fromordinal(int(round(np.median(days)))).isoformat() if len(days) else None
    q1, q3 = (dt.date.fromordinal(int(round(np.quantile(days, q)))).isoformat() for q in (0.25, 0.75)) if len(days) \
        else (None, None)
    return {"p_site": round(p_site, 4), "p_ctrl": round(p_ctrl, 4),
            "ratio": round(p_site / p_ctrl, 3) if p_ctrl > 0 else None,
            "D_sar": med, "D_sar_q1": q1, "D_sar_q3": q3, "site_pixels_with_dark": int(ok.sum())}


def fy_mean(stack, dates, fy, pol, rows):
    sel = [i for i, d in enumerate(dates) if fy[0] <= d <= fy[1]]
    return np.nanmean(np.asarray(stack[pol, sel, rows[0]:rows[1]], float), axis=0)


def tile_scores(changed, valid, key, ids):
    out = {}
    for i in ids:
        m = (key == i) & valid
        out[i] = float(changed[m].sum() / m.sum()) if m.sum() else float("nan")
    return out


def b_observables(score, ids, labels, builtup, exclude=()):
    use = [i for i in ids if i not in exclude]
    pos2 = {i for i in use if labels[i] == "2"}
    pos12 = {i for i in use if labels[i] in ("1", "2")}
    k = round(0.2 * len(use))
    s = [score[i] for i in use]
    b = [builtup[i] for i in use]
    order = rank_order(s, use)
    hits = len(set(order[:k]) & pos2)
    rec, rec_b = recall_at(s, use, pos2, k), recall_at(b, use, pos2, k)
    return {"tiles": len(use), "k": k, "positives_2": len(pos2), "hits_2": hits,
            "recall_2_sar": round(rec, 4), "recall_2_builtup": round(rec_b, 4), "diff": round(rec - rec_b, 4),
            "p_random_at_least_hits": round(hypergeom_tail(hits, len(use), len(pos2), k), 6),
            "recall_12_sar": round(recall_at(s, use, pos12, k), 4),
            "recall_12_builtup": round(recall_at(b, use, pos12, k), 4),
            "site_rank": order.index(SITE_TILE) + 1 if SITE_TILE in use else None,
            "top_k_labels": {v: sum(labels[i] == v for i in order[:k]) for v in ("0", "1", "2")}}


def main():
    stack = np.load(ART / "stack.npy", mmap_mode="r")
    aux = np.load(ART / "aux.npz")
    dates = [str(d) for d in aux["dates"]]
    site, ctrl, wc = aux["site"], aux["ctrl"], aux["wc"]
    key = np.char.add(np.char.add(aux["tile_x"].astype(str), "_"), aux["tile_y"].astype(str))
    labels = {}
    with open(HERE.parent / "labels/labels.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["label"] != "NA":
                labels[f"{r['tile_x']}_{r['tile_y']}"] = r["label"]
    ids = sorted(labels)
    s2 = json.loads((OUT / "s2_break.json").read_text(encoding="utf-8"))
    out = {"settings": {"alpha": ALPHA, "enl": ENL, "W": W, "FY2019": FY2019, "FY2024": FY2024},
           "site_pixels": int(site.sum()), "ctrl_pixels": int(ctrl.sum()), "D_opt": s2["D_opt"]}

    # A1, A2
    m = site | ctrl
    is_site = site[m]
    main_res = run_seq(stack, m, ENL, ALPHA)
    a = a_observables(main_res, dates, is_site)
    a["D_gap_days"] = abs(ordinal(a["D_sar"]) - ordinal(s2["D_opt"])) if a["D_sar"] else None
    out["A"] = a
    out["C1"] = "supported" if a["p_site"] >= 0.5 and a["p_site"] >= 2 * a["p_ctrl"] else "rejected"
    out["C2"] = "supported" if a["D_gap_days"] is not None and a["D_gap_days"] <= 90 else "rejected"
    np.savez_compressed(ART / "change_site_ctrl.npz", change=main_res["change"], ratio_db=main_res["ratio_db"].astype(np.float32),
                        is_site=is_site, dates=np.array(dates))
    av = {}
    for name, L, al, pols in (("alpha_0.0001", ENL, 1e-4, (0, 1)), ("alpha_0.01", ENL, 1e-2, (0, 1)),
                              ("enl_3.3", 3.3, ALPHA, (0, 1)), ("enl_5.5", 5.5, ALPHA, (0, 1)),
                              ("vv_only", ENL, ALPHA, (0,))):
        r = a_observables(run_seq(stack, m, L, al, pols), dates, is_site)
        r["D_gap_days"] = abs(ordinal(r["D_sar"]) - ordinal(s2["D_opt"])) if r["D_sar"] else None
        av[name] = r
        print("A", name, r, flush=True)
    out["A_variants"] = av

    # per-date series of SITE and CTRL
    dark = main_res["change"] & (main_res["ratio_db"] < 0)
    with open(OUT / "site_series.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "site_vv_db", "site_vh_db", "ctrl_vv_db", "ctrl_vh_db", "site_dark_share", "ctrl_dark_share"])
        for t, d in enumerate(dates):
            v = [10 * np.log10(np.nanmean(np.asarray(stack[k, t][s], float))) for s in (site, ctrl) for k in (0, 1)]
            w.writerow([d, round(v[0], 3), round(v[1], 3), round(v[2], 3), round(v[3], 3),
                        round(float(dark[t][is_site].mean()), 4), round(float(dark[t][~is_site].mean()), 4)])

    # B: tile scores
    rows, cols = site.shape
    d19 = np.empty((2, rows, cols))
    d24 = np.empty((2, rows, cols))
    for k in (0, 1):
        d19[k] = fy_mean(stack, dates, FY2019, k, (0, rows))
        d24[k] = fy_mean(stack, dates, FY2024, k, (0, rows))
    ddb = np.abs(10 * np.log10(d24 / d19))
    valid = np.all(np.isfinite(ddb), axis=0) & (wc != 80)
    builtup = tile_scores(wc == 50, valid, key, ids)
    scores = {}
    for thr in (2.0, 3.0, 4.0):
        scores[f"db{thr:g}"] = tile_scores((ddb >= thr).any(0), valid, key, ids)
    scores["db3_vv"] = tile_scores(ddb[0] >= 3.0, valid, key, ids)

    # B variant: change points over all pixels (main settings), any change in W
    inw = np.array([W[0] <= d <= W[1] for d in dates])
    anych = np.zeros((rows, cols), bool)
    step = 40
    for r0 in range(0, rows, step):
        m2 = np.zeros((rows, cols), bool)
        m2[r0:r0 + step] = True
        res = run_seq(stack, m2, ENL, ALPHA)
        anych[r0:r0 + step] = res["change"][inw].any(0).reshape(-1, cols)
        print("rows", r0, flush=True)
    scores["changepoint"] = tile_scores(anych, valid, key, ids)

    main_s = scores["db3"]
    b = b_observables(main_s, ids, labels, builtup)
    out["B"] = b
    out["C3"] = "supported" if b["site_rank"] <= 6 else "rejected"
    out["C4"] = "supported" if b["recall_2_sar"] >= 0.5 and b["diff"] >= 0.2 else "rejected"
    sx, sy = map(int, SITE_TILE.split("_"))
    near = {f"{sx + i}_{sy + j}" for i in (-1, 0, 1) for j in (-1, 0, 1)}
    out["B_variants"] = {name: b_observables(scores[name], ids, labels, builtup)
                         for name in ("db2", "db4", "db3_vv", "changepoint")}
    out["B_variants"]["exclude_site_and_neighbours"] = b_observables(main_s, ids, labels, builtup, exclude=near)
    out["B_capture_curve"] = {}
    for name, sc in (("sar", main_s), ("builtup", builtup)):
        order = rank_order([sc[i] for i in ids], ids)
        pos2 = [i for i in ids if labels[i] == "2"]
        out["B_capture_curve"][name] = [sum(labels[i] == "2" for i in order[:k]) for k in range(len(ids) + 1)]
    out["B_capture_curve"]["positives_2"] = len([i for i in ids if labels[i] == "2"])

    ranks = {name: {i: n + 1 for n, i in enumerate(rank_order([sc[i] for i in ids], ids))}
             for name, sc in list(scores.items()) + [("builtup", builtup)]}
    with open(OUT / "tiles.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        names = list(scores)
        w.writerow(["tile", "label", "builtup_share", "rank_builtup"] + [f"score_{n}" for n in names] +
                   [f"rank_{n}" for n in names])
        for i in ids:
            w.writerow([i, labels[i], round(builtup[i], 4), ranks["builtup"][i]] + [round(scores[n][i], 4) for n in names]
                       + [ranks[n][i] for n in names])
    np.savez_compressed(ART / "fy_ddb.npz", ddb=ddb.astype(np.float32), valid=valid, anych=anych)
    (OUT / "blocks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("A", "C1", "C2", "B", "C3", "C4")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
