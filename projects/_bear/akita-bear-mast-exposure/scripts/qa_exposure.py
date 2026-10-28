"""Checks of the exposure before it meets the bear reports: distributions, zeros, correlations, municipalities,
Spearman with the saved B_env surfaces, and agreement with the forest resource mesh (natural forest, broad-leaved
trees, forest register), which is used here only as a check.

    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy \
      --with scipy python qa_exposure.py BEAR_ART ART OUT_JSON
"""

import json
import os
import sys

import numpy as np

MESH = ("hf://datasets/yuiseki/akita-forest-resource-mesh-2026@1cad01a041ad2e1bfc2fa9ba35bd1385070d3f5f/"
        "parquet/*.parquet")
FEATS = [f"{c}_fraction_{r}" for r in ("500", "2000") for c in ("beech", "beech_mizunara", "mizunara", "konara", "beech_oak")]
SURFACES = {"b1_2024": "b1_dev_2023_to_2024", "b2_2025": "b2_confirm_2023-2024_to_2025", "b3_2026": "b3_confirm_2023-2025_to_2026"}


def mesh_index(cell_x, cell_y, x0, y0):
    """100 m cell of each 20 m mesh cell, by the 20 m cell's centre (cell_x, cell_y is its lower-left corner)."""
    return np.floor((cell_x + 10 - x0) / 100).astype(int), np.floor((cell_y + 10 - y0) / 100).astype(int)


def share_in(area, other, thr):
    """Share of the area that lies in cells whose `other` value is at least thr."""
    return float(area[other >= thr].sum() / area.sum())


def describe(v):
    f = v[np.isfinite(v)]
    q = np.quantile(f, [0.1, 0.25, 0.5, 0.75, 0.9, 0.99])
    return {"n": int(f.size), "n_nan": int((~np.isfinite(v)).sum()), "zero_share": float((f == 0).mean()), "mean": float(f.mean()),
            "q10": q[0], "q25": q[1], "median": q[2], "q75": q[3], "q90": q[4], "q99": q[5], "max": float(f.max())}


def mesh_cells(grid, cache):
    """[ny, nx] counts of 20 m mesh cells: all, forest register (林種 not NULL), natural forest, broad-leaved, both."""
    if not os.path.exists(cache):
        import duckdb

        con = duckdb.connect()
        con.sql("SET memory_limit='8GB'")
        x0, y0 = grid["x0"], grid["y0"]
        df = con.sql(f"""SELECT floor((cell_x + 10 - {x0}) / 100)::INT ix, floor((cell_y + 10 - {y0}) / 100)::INT iy,
            count(*) n, count(林種) reg, count(*) FILTER (林種 = '天然林') nat, count(*) FILTER (森林簿樹種1 = '広葉樹') bl,
            count(*) FILTER (林種 = '天然林' AND 森林簿樹種1 = '広葉樹') natbl
            FROM read_parquet('{MESH}') GROUP BY ALL""").fetchnumpy()
        np.savez_compressed(cache, **df)
    d = np.load(cache)
    out = {}
    ok = (d["ix"] >= 0) & (d["ix"] < grid["nx"]) & (d["iy"] >= 0) & (d["iy"] < grid["ny"])
    for k in ("n", "reg", "nat", "bl", "natbl"):
        a = np.zeros((grid["ny"], grid["nx"]))
        np.add.at(a, (d["iy"][ok], d["ix"][ok]), d[k][ok])
        out[k] = a
    out["off_grid"] = int((~ok).sum())
    return out


def main():
    from scipy.stats import spearmanr

    import exposure as ex

    bear, art, out_json = sys.argv[1:4]
    grid = json.load(open(f"{bear}/grid.json"))
    muni = np.load(f"{bear}/grid_mask.npz")["muni"]
    inside = muni >= 0
    e = np.load(f"{art}/exposure.npz")
    res = {"exposure_npz": f"{art}/exposure.npz", "note_nan": "NaN = no mapped vegetation within the radius (water, see tracker)"}
    res["distribution"] = {f: describe(e[f][inside]) for f in FEATS}
    X = np.column_stack([e[f][inside] for f in FEATS])
    ok = np.isfinite(X).all(axis=1)
    rho = spearmanr(X[ok]).statistic
    res["spearman_between_features"] = {"features": FEATS, "matrix": np.round(rho, 3).tolist(), "rows": int(ok.sum())}
    by = {}
    for i, name in enumerate(grid["names"]):
        m = inside & (muni == i)
        by[name] = {"cells": int(m.sum())} | {f: {"mean": float(np.nanmean(e[f][m])), "zero_share": float(np.nanmean(e[f][m] == 0))}
                                              for f in ("beech_oak_fraction_500", "beech_oak_fraction_2000")}
    res["by_municipality"] = by
    res["spearman_with_B_env"] = {}
    for k, f in SURFACES.items():
        s = np.load(f"{bear}/eval/{f}_scores.npz")["B_env"].astype(float)
        res["spearman_with_B_env"][k] = {g: float(spearmanr(s[np.isfinite(e[g][inside])], e[g][inside][np.isfinite(e[g][inside])]).statistic) for g in FEATS}
    mc = mesh_cells(grid, f"{art}/mesh_cells.npz")
    cell_bo = e["cell_beech_oak"].astype(float)
    n = np.where(mc["n"] > 0, mc["n"], np.nan)
    with np.errstate(invalid="ignore"):
        share = {k: mc[k] / n for k in ("reg", "nat", "bl", "natbl")}
    m = inside & np.isfinite(share["reg"])
    area = cell_bo[m]
    res["mesh"] = {
        "mesh": MESH, "mesh_cells_counted": float(mc["n"].sum()), "mesh_groups_off_grid": mc["off_grid"],
        "prefecture_cells_with_mesh": int(m.sum()),
        "beech_oak_area_share_in_cells_with": {f"{k}_ge_0.5": share_in(area, share[k][m], 0.5) for k in ("reg", "nat", "bl", "natbl")},
        "beech_oak_area_in_cells_without_mesh_km2": float(cell_bo[inside & ~np.isfinite(share["reg"])].sum() / 1e4),
        "gate_reg_share_ge_0.70": share_in(area, share["reg"][m], 0.5) >= 0.70,
    }
    k5 = ex.disk(5)
    natbl500 = ex.disk_sum(mc["natbl"], k5) / np.where(ex.disk_sum(mc["n"], k5) > 0, ex.disk_sum(mc["n"], k5), np.nan)
    v = inside & np.isfinite(natbl500) & np.isfinite(e["beech_oak_fraction_500"])
    res["mesh"]["spearman_beech_oak_500_vs_natural_broadleaf_500"] = float(spearmanr(e["beech_oak_fraction_500"][v], natbl500[v]).statistic)
    allveg = np.load(f"{art}/exposure.npz")["cell_any"].astype(float)
    nonbo = (allveg - cell_bo)[m]
    res["mesh"]["other_vegetation_area_share_in_cells_with_natbl_ge_0.5"] = share_in(nonbo, share["natbl"][m], 0.5)
    json.dump(res, open(out_json, "w"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps({k: v for k, v in res.items() if k not in ("by_municipality", "spearman_between_features")}, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
