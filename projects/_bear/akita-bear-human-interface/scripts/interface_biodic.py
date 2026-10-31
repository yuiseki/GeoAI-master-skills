"""How far two observation processes agree: the Ministry of the Environment's bear distribution mesh (yo4, information
of fiscal 2010-2017) and the report-trained proxies M_B and M_H. Exploratory, run once (EXPERIMENT_PLAN.md,
2026-10-31). Not a validation of the bear distribution: both are records of what people observed.

Unit: the 5 km meshes holding at least 1,200 of the prefecture's 100 m cells (by cell centre). Record level per
mesh: 0 no information in 2010-2017 and not confirmed in the 6th survey, 1 one of the two, 2 both. Mesh value of a
proxy: the mean of its prefecture percentile over the mesh's cells. Main statistic: Spearman rho of the level with
each mesh value, and rho(M_B) - rho(M_H) with a block bootstrap over 2nd-order meshes (6-digit codes).

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 \
      --with scipy --with pandas --with pyarrow --with pyproj --with shapely --with scikit-learn==1.9.1 python \
      projects/_bear/akita-bear-human-interface/scripts/interface_biodic.py artifacts/_bear/akita-bear-risk-grid-100m \
      artifacts/_bear/akita-bear-human-interface projects/_bear/akita-bear-human-interface/outputs/biodic_consistency.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

import interface_models as im
import phase as ph

REV = "7f635cbfb92be5093fa707dbe6afec0e37d240f4"
SOURCE = f"hf://datasets/yuiseki/env-biodic-bear-distribution-mesh-jp@{REV}/parquet/bear_mesh_long.parquet"
MIN_CELLS = 1200
AXES = {"B3": "b3_confirm_2023-2025_to_2026.npz", "B2": "b2_confirm_2023-2024_to_2025.npz"}


def mesh5_code(lon, lat):
    """8-digit 5 km mesh code: the 2nd-order mesh, then 2 or 7 for the south/west or north/east half (data card)."""
    a = lat * 1.5
    p, u = np.floor(a).astype(int), np.floor(lon - 100).astype(int)
    fa, fo = (a - p) * 8, (lon - 100 - u) * 8
    q, v = np.floor(fa).astype(int), np.floor(fo).astype(int)
    r, w = np.where(fa - q >= 0.5, 7, 2), np.where(fo - v >= 0.5, 7, 2)
    return np.array([f"{a_:02d}{b_:02d}{c}{d}{e}{f}" for a_, b_, c, d, e, f in zip(p, u, q, v, r, w)])


def record_level(h22_29, sixth):
    return (np.asarray(h22_29) == "1").astype(int) + (np.asarray(sixth) == "1").astype(int)


def spearman_diff(level, a, b, blocks, B=1000, seed=0):
    """rho(level, a) - rho(level, b), and its 90% interval resampling whole blocks."""
    from scipy.stats import spearmanr

    def d(idx):
        return spearmanr(level[idx], a[idx]).statistic - spearmanr(level[idx], b[idx]).statistic

    u, inv = np.unique(blocks, return_inverse=True)
    members = [np.flatnonzero(inv == k) for k in range(len(u))]
    rng = np.random.default_rng(seed)
    boot = np.array([d(np.concatenate([members[k] for k in rng.integers(0, len(u), len(u))])) for _ in range(B)])
    return float(d(np.arange(len(level)))), float(np.quantile(boot, 0.05)), float(np.quantile(boot, 0.95))


def reading(lo, hi):
    if lo > 0:
        return "M_B agrees with the Ministry record more than M_H: limited external validity for the name bear-side"
    if hi < 0:
        return "the Ministry record agrees more with the human-side proxy: the other observation process also follows observation opportunity"
    return "no difference: M_B carries much of the reporting process"


def main():
    import duckdb
    import pandas as pd
    import pyproj
    import shapely
    from scipy.stats import spearmanr
    from sklearn.metrics import roc_auc_score

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("out", type=Path)
    args = a.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; this check runs once")
    hashes = im.check_inputs(args.art)
    meta = json.loads((args.art / "grid.json").read_text(encoding="utf-8"))
    cells = pd.read_parquet(args.art / "cells.parquet", columns=["ix", "iy"])
    x = meta["x0"] + (cells.ix.to_numpy() + 0.5) * meta["size"]
    y = meta["y0"] + (cells.iy.to_numpy() + 0.5) * meta["size"]
    lon, lat = pyproj.Transformer.from_crs("EPSG:6678", "EPSG:6668", always_xy=True).transform(x, y)
    code = mesh5_code(lon, lat)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    yo = con.execute(f"""SELECT mesh_code, H22_29, "第6回で確" AS sixth, ST_AsWKB(geometry) AS g
                         FROM read_parquet('{SOURCE}') WHERE survey_id = 'yo4'""").df()
    yo = yo[yo.mesh_code.isin(set(code))].reset_index(drop=True)
    cen = shapely.centroid(shapely.from_wkb(yo.g.apply(bytes).to_numpy()))
    back = mesh5_code(shapely.get_x(cen), shapely.get_y(cen))
    if not np.array_equal(back, yo.mesh_code.to_numpy()):
        raise ValueError("computed mesh codes do not match the yo4 polygons")
    n_cells = pd.Series(code).value_counts()
    keep = yo[yo.mesh_code.map(n_cells) >= MIN_CELLS].reset_index(drop=True)
    level = record_level(keep.H22_29, keep.sixth)
    blocks = keep.mesh_code.str[:6].to_numpy()
    inside = np.load(args.art / "grid_mask.npz")["muni"] >= 0
    full = np.load(args.art / "reports_by_year.npz")
    reported = (full["c2023"] + full["c2024"] + full["c2025"] + full["c2026"])[inside] > 0
    frame = pd.DataFrame({"code": code, "reported": reported})
    res = {"mode": "exploratory, run once; consistency of two observation processes, not a validation",
           "source": SOURCE, "min_cells": MIN_CELLS, "n_meshes_touching": int(len(n_cells)),
           "n_meshes_in_yo4": int(len(yo)), "n_meshes_used": int(len(keep)),
           "level_counts": {str(k): int(v) for k, v in zip(*np.unique(level, return_counts=True))},
           "polygon_code_check": "all yo4 polygon centroids give their own code", "input_sha256": hashes,
           "axes": {}}
    res["reported_share_note"] = "share of a mesh's cells with a report in bear years 2023-2026 (2026: April-September)"
    rep = frame.groupby("code").reported.mean().reindex(keep.mesh_code).to_numpy()
    for name, f in AXES.items():
        z = np.load(args.work / "scores" / f)
        frame["b"] = ph.percentile(z["M_B"].astype(float))
        frame["h"] = ph.percentile(z["M_H"].astype(float))
        g = frame.groupby("code")[["b", "h"]].mean().reindex(keep.mesh_code)
        mb, mh = g.b.to_numpy(), g.h.to_numpy()
        d, lo, hi = spearman_diff(level, mb, mh, blocks)
        any_rec = (keep.H22_29 == "1").to_numpy()
        among = any_rec
        both = (keep.sixth == "1").to_numpy()[among]  # confirmed also in the 6th survey
        row = {"axis": f, "rho_M_B": float(spearmanr(level, mb).statistic), "rho_M_H": float(spearmanr(level, mh).statistic),
               "rho_reported_share": float(spearmanr(level, rep).statistic),
               "rho_diff_B_minus_H": d, "lo90": lo, "hi90": hi, "reading": reading(lo, hi),
               "auc_2010_17_record": {"M_B": float(roc_auc_score(any_rec, mb)), "M_H": float(roc_auc_score(any_rec, mh)),
                                      "reported_share": float(roc_auc_score(any_rec, rep))},
               "auc_also_6th_among_2010_17": {"M_B": float(roc_auc_score(both, mb[among])),
                                             "M_H": float(roc_auc_score(both, mh[among])),
                                             "reported_share": float(roc_auc_score(both, rep[among]))},
               "mean_pct_by_level": {str(k): {"M_B": float(mb[level == k].mean()), "M_H": float(mh[level == k].mean()),
                                              "reported_share": float(rep[level == k].mean())} for k in (0, 1, 2)}}
        res["axes"][name] = row
        print(name, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items() if k != "mean_pct_by_level"})
        print("   by level", {k: {m: round(x, 4) for m, x in v.items()} for k, v in row["mean_pct_by_level"].items()})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(res["n_meshes_used"], res["level_counts"])


if __name__ == "__main__":
    main()
