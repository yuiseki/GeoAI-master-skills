"""Freeze the 5 km mesh inputs: covariates, the Ministry records (yo4) and the Kumadas April-September counts.

Each 100 m prefecture cell goes to the 5 km mesh holding its centre (interface_biodic.mesh5_code; the yo4 polygons
are checked to give their own codes). Per mesh: the number of prefecture cells, the core flag (>= 1,200 cells), the
municipality with the most cells, the bear-side prior covariates (cell means of tree, water, elev, slope and
log1p(d_stream)), the human-side measurements (log1p of the summed people and buildings, crop and built means, the
share of cells within 100 m of a road), the yo4 flags (第6回で確 = E6, H22_29 = E7) and the April-September report
counts of 2023-2026. H is the first principal component of the five standardised human-side measurements over the
core meshes (sign: people load positive), standardised; reports are not used.

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 \
      --with scipy --with pandas --with pyarrow --with pyproj --with shapely --with scikit-learn==1.9.1 python \
      projects/_bear/akita-bear-latent-observation-model/scripts/align_inputs.py artifacts/_bear/akita-bear-risk-grid-100m \
      artifacts/_bear/akita-bear-human-interface artifacts/_bear/akita-bear-latent-observation-model/mesh \
      projects/_bear/akita-bear-latent-observation-model/outputs/inputs_summary.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

YEARS = (2023, 2024, 2025, 2026)
MIN_CELLS = 1200
EXPECTED_CORE = 480
B_COLS = ["tree", "water", "elev", "slope", "log_d_stream"]
H_COLS = ["log_pop", "log_bldg", "crop", "built", "road_share"]


def pc1(Z, sign_col=0):
    """First principal component of the standardised columns of Z (rows: meshes), sign so that column sign_col
    loads positive. Returns (scores standardised, loadings, share of variance)."""
    Zs = (Z - Z.mean(0)) / Z.std(0)
    vals, vecs = np.linalg.eigh(np.cov(Zs.T))
    v = vecs[:, -1]
    if v[sign_col] < 0:
        v = -v
    s = Zs @ v
    return (s - s.mean()) / s.std(), v, float(vals[-1] / vals.sum())


def standardise(X):
    return (X - X.mean(0)) / X.std(0)


def main():
    import duckdb
    import pandas as pd
    import pyproj
    import shapely

    import interface_biodic as ib
    import interface_models as im

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("hi_work", type=Path, help="artifacts of akita-bear-human-interface (labels/reports.parquet)")
    a.add_argument("outdir", type=Path)
    a.add_argument("summary", type=Path)
    args = a.parse_args()
    hashes = im.check_inputs(args.art)
    meta = json.loads((args.art / "grid.json").read_text(encoding="utf-8"))
    muni_grid = np.load(args.art / "grid_mask.npz")["muni"]
    inside = muni_grid >= 0
    cells = pd.read_parquet(args.art / "cells.parquet", columns=["ix", "iy"])
    x = meta["x0"] + (cells.ix.to_numpy() + 0.5) * meta["size"]
    y = meta["y0"] + (cells.iy.to_numpy() + 0.5) * meta["size"]
    lon, lat = pyproj.Transformer.from_crs("EPSG:6678", "EPSG:6668", always_xy=True).transform(x, y)
    code = ib.mesh5_code(lon, lat)
    wc, dem, pop, osm = (np.load(args.art / f"{n}.npz") for n in ("worldcover", "dem", "worldpop", "osm"))
    cell = pd.DataFrame({"mesh": code, "muni": muni_grid[inside],
                         "tree": wc["f10"][inside], "water": wc["f80"][inside], "crop": wc["f40"][inside],
                         "built": wc["f50"][inside], "elev": dem["elev"][inside], "slope": dem["slope"][inside],
                         "log_d_stream": np.log1p(osm["d_stream"][inside]), "pop": pop["pop"][inside],
                         "bldg": osm["n_building"][inside], "near_road": osm["d_road"][inside] <= 100})
    g = cell.groupby("mesh")
    mesh = pd.DataFrame({"n_cells": g.size(), "muni": g.muni.agg(lambda s: s.value_counts().idxmax()),
                         **{c: g[c].mean() for c in ("tree", "water", "elev", "slope", "log_d_stream", "crop", "built")},
                         "log_pop": np.log1p(g["pop"].sum()), "log_bldg": np.log1p(g["bldg"].sum()),
                         "road_share": g.near_road.mean()})
    mesh["core"] = mesh.n_cells >= MIN_CELLS
    if int(mesh.core.sum()) != EXPECTED_CORE:
        raise ValueError(f"{int(mesh.core.sum())} core meshes, expected {EXPECTED_CORE}")
    if mesh.loc[mesh.core, B_COLS + H_COLS].isna().any().any():
        raise ValueError("a core mesh covariate is missing")
    n_missing_noncore = int(mesh.loc[~mesh.core, B_COLS + H_COLS].isna().any(axis=1).sum())
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    yo = con.execute(f"""SELECT mesh_code, H22_29, "第6回で確" AS sixth, ST_AsWKB(geometry) AS g
                         FROM read_parquet('{ib.SOURCE}') WHERE survey_id = 'yo4'""").df()
    yo = yo[yo.mesh_code.isin(set(mesh.index))]
    cen = shapely.centroid(shapely.from_wkb(yo.g.apply(bytes).to_numpy()))
    if not np.array_equal(ib.mesh5_code(shapely.get_x(cen), shapely.get_y(cen)), yo.mesh_code.to_numpy()):
        raise ValueError("computed mesh codes do not match the yo4 polygons")
    yo = yo.set_index("mesh_code")
    mesh["in_yo4"] = mesh.index.isin(yo.index)
    mesh["E6"] = yo.sixth.reindex(mesh.index).map({"1": 1, "0": 0})
    mesh["E7"] = yo.H22_29.reindex(mesh.index).map({"1": 1, "0": 0})
    rep = pd.read_parquet(args.hi_work / "labels/reports.parquet")
    rep = rep[rep.in_season & (rep.cell >= 0) & rep.bear_year.isin(YEARS)]
    rep["mesh"] = code[rep.cell.to_numpy()]
    counts = rep.groupby(["mesh", "bear_year"]).size().unstack(fill_value=0).reindex(index=mesh.index, columns=list(YEARS), fill_value=0)
    for yr in YEARS:
        mesh[f"Y{yr}"] = counts[yr].astype(int)
    core = mesh[mesh.core].copy()
    Hs, load, share = pc1(core[H_COLS].to_numpy())
    core["H"] = Hs
    Xb = standardise(core[B_COLS].to_numpy())
    for j, c in enumerate(B_COLS):
        core[f"zB_{c}"] = Xb[:, j]
    core["z_tree"] = core["zB_tree"]
    mesh = mesh.join(core[["H"] + [f"zB_{c}" for c in B_COLS]])
    args.outdir.mkdir(parents=True, exist_ok=True)
    mesh.reset_index(names="mesh_code").to_parquet(args.outdir / "mesh_table.parquet", index=False)
    rep_total = {str(yr): int(rep[rep.bear_year == yr].shape[0]) for yr in YEARS}
    summary = {
        "derived": "mesh aggregates of observed records and covariates; not a model output",
        "input_sha256": {**hashes, "reports.parquet": im.sha256(args.hi_work / "labels/reports.parquet")},
        "yo4_source": ib.SOURCE, "min_cells": MIN_CELLS,
        "meshes_touching": int(len(mesh)), "meshes_in_yo4": int(mesh.in_yo4.sum()), "core_meshes": int(mesh.core.sum()),
        "noncore_meshes_with_a_missing_covariate": n_missing_noncore,
        "core_E6_rate": float(core.E6.mean()), "core_E7_rate": float(core.E7.mean()),
        "core_E6_E7_table": {f"E6={i},E7={j}": int(((core.E6 == i) & (core.E7 == j)).sum()) for i in (0, 1) for j in (0, 1)},
        "core_mean_count": {str(yr): float(core[f"Y{yr}"].mean()) for yr in YEARS},
        "core_total_count": {str(yr): int(core[f"Y{yr}"].sum()) for yr in YEARS},
        "prefecture_reports_apr_sep": rep_total,
        "core_zero_share": {str(yr): float((core[f"Y{yr}"] == 0).mean()) for yr in YEARS},
        "core_count_var_to_mean": {str(yr): float(core[f"Y{yr}"].var() / core[f"Y{yr}"].mean()) for yr in YEARS},
        "core_municipalities": int(core.muni.nunique()),
        "H_pc1": {"columns": H_COLS, "loadings": load.round(4).tolist(), "variance_share": share},
        "B_prior_columns": B_COLS,
        "corr_H_tree": float(np.corrcoef(core.H, core.zB_tree)[0, 1]),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(args.summary, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
