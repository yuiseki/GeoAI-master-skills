"""Assign WorldPop 100 m pixels to 1 km meshes and audit NoData / zero / outside.

Run from repository root with the analysis venv:
  /tmp/venv-geoai/bin/python projects/elderly-transit-100m-allocation/scripts/assign_worldpop.py
"""

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.name
OUTPUT = PROJECT / "outputs"

ADMIN_REV = "e6c87b1d7095c17422147962185071a986e13135"
ADMIN = f"hf://datasets/yuiseki/jp-admin-2026-09@{ADMIN_REV}/municipalities.parquet"
NODATA = -99999.0


def mesh_bounds(code):
    south = int(code[:2]) / 1.5 + int(code[4]) / 12 + int(code[6]) / 120
    west = 100 + int(code[2:4]) + int(code[5]) / 8 + int(code[7]) / 80
    return west, south, west + 1 / 80, south + 1 / 120


def codes_from_lonlat(lon, lat):
    lat_code = np.floor(lat * 1.5).astype(np.int64)
    lon_code = np.floor(lon).astype(np.int64) - 100
    p = np.floor((lat * 1.5 - lat_code) * 8).astype(np.int64)
    q = np.floor((lon - np.floor(lon)) * 8).astype(np.int64)
    r = np.floor(lat * 120 - lat_code * 80 - p * 10).astype(np.int64)
    s = np.floor((lon - 100 - lon_code) * 80 - q * 10).astype(np.int64)
    if any((v < 0).any() or (v > 9).any() for v in (p, q, r, s)):
        raise ValueError("mesh sub-index out of range")
    return [
        f"{a:02d}{b:02d}{c}{d}{e}{f}"
        for a, b, c, d, e, f in zip(lat_code, lon_code, p, q, r, s)
    ]


def main():
    con = duckdb.connect()
    con.execute("install spatial; load spatial; install httpfs; load httpfs")
    mainland_wkb = con.execute(
        f"""select ST_AsWKB(ST_Transform(ST_Union_Agg(geometry),
              'EPSG:4612','EPSG:4326', always_xy := true))
            from '{ADMIN}' where pref_code='13'
              and (code5 between '13101' and '13123' or code5 like '132%'
                   or code5 in ('13303','13305','13307','13308'))"""
    ).fetchone()[0]
    mainland = shapely.from_wkb(bytes(mainland_wkb))

    meshes = pd.read_parquet(ARTIFACTS / "meshes.parquet")
    mesh_set = set(meshes["mesh"])
    mesh_bounds_map = {code: mesh_bounds(code) for code in mesh_set}

    data = np.load(ARTIFACTS / "worldpop-window.npz")
    lon_grid, lat_grid, values = data["lon"], data["lat"], data["values"]
    lon, lat = np.meshgrid(lon_grid, lat_grid)
    lon = lon.ravel()
    lat = lat.ravel()
    values = values.ravel()
    inside = shapely.contains_xy(mainland, lon, lat)
    codes = codes_from_lonlat(lon, lat)
    codes = np.asarray(codes, dtype=object)

    in_mesh = np.array([c in mesh_set for c in codes], dtype=bool)
    status = np.full(values.shape, "positive", dtype=object)
    status[values == 0] = "zero"
    status[values == NODATA] = "nodata"

    # Validate that each centre falls inside its computed mesh.
    sample = np.flatnonzero(inside & in_mesh)
    bad = 0
    for i in sample[:: max(1, len(sample) // 2000)]:
        west, south, east, north = mesh_bounds_map[codes[i]]
        if not (west <= lon[i] < east and south <= lat[i] < north):
            bad += 1
    if bad:
        raise ValueError(f"{bad} sampled pixel centres fall outside their mesh")

    frame = pd.DataFrame(
        {
            "pixel_id": np.arange(values.size),
            "mesh": codes,
            "lon": lon,
            "lat": lat,
            "value": values,
            "status": status,
            "inside_mainland": inside,
            "in_mesh": in_mesh,
        }
    )
    frame.to_parquet(ARTIFACTS / "worldpop-pixels.parquet", index=False)

    selected = frame[frame["inside_mainland"] & frame["in_mesh"]].copy()
    selected["is_valid"] = selected["status"] != "nodata"
    selected["is_nodata"] = selected["status"] == "nodata"
    selected["is_zero"] = selected["status"] == "zero"
    selected["is_positive"] = selected["status"] == "positive"
    selected["value_valid"] = selected["value"].where(selected["is_valid"], 0.0)
    agg = (
        selected.groupby("mesh")
        .agg(
            pixels_inside=("pixel_id", "size"),
            valid_pixels=("is_valid", "sum"),
            nodata_pixels=("is_nodata", "sum"),
            zero_pixels=("is_zero", "sum"),
            positive_pixels=("is_positive", "sum"),
            wpop_sum=("value_valid", "sum"),
            wpop_max=("value", "max"),
        )
        .reset_index()
    )
    full = frame[frame["in_mesh"]].copy()
    full["is_nodata"] = full["status"] == "nodata"
    full_counts = (
        full.groupby("mesh")
        .agg(pixels_full=("pixel_id", "size"), pixels_full_nodata=("is_nodata", "sum"))
        .reset_index()
    )
    agg = agg.merge(full_counts, on="mesh", how="outer")
    agg = agg.merge(meshes[["mesh", "total", "age65", "age75", "municipality_code", "municipality"]], on="mesh", how="left")
    agg["wpop_census_ratio"] = agg["wpop_sum"] / agg["total"].where(agg["total"] > 0)
    agg["inside_share_of_full"] = agg["pixels_inside"] / agg["pixels_full"].where(agg["pixels_full"] > 0)
    agg.to_parquet(ARTIFACTS / "worldpop-mesh.parquet", index=False)

    in23 = meshes["municipality_code"].str.startswith("131")
    mesh23 = set(meshes.loc[in23, "mesh"])
    wpop23 = float(agg.loc[agg["mesh"].isin(mesh23), "wpop_sum"].sum())
    census23 = int(meshes.loc[in23, "total"].sum())
    audit = {
        "window_pixels": int(values.size),
        "inside_mainland_pixels": int(inside.sum()),
        "inside_and_in_mesh_pixels": int((inside & in_mesh).sum()),
        "inside_but_not_in_mesh_pixels": int((inside & ~in_mesh).sum()),
        "outside_mainland_in_mesh_pixels": int((~inside & in_mesh).sum()),
        "inside_nodata_pixels": int(((status == "nodata") & inside).sum()),
        "inside_zero_pixels": int(((status == "zero") & inside).sum()),
        "inside_positive_pixels": int(((status == "positive") & inside).sum()),
        "inside_valid_sum": float(values[inside & (values != NODATA)].sum()),
        "meshes_with_pixels": int(agg["mesh"].nunique()),
        "meshes_missing_all_pixels": sorted(mesh_set - set(agg["mesh"])),
        "pixels_full_distribution": {
            str(k): int(v) for k, v in agg["pixels_full"].value_counts().sort_index().items()
        },
        "pixels_inside_distribution": {
            str(k): int(v) for k, v in agg["pixels_inside"].value_counts().sort_index().items()
        },
        "wpop_census_ratio": {
            "count": int(agg["wpop_census_ratio"].notna().sum()),
            "median": float(agg["wpop_census_ratio"].median()),
            "q25": float(agg["wpop_census_ratio"].quantile(0.25)),
            "q75": float(agg["wpop_census_ratio"].quantile(0.75)),
            "min": float(agg["wpop_census_ratio"].min()),
            "max": float(agg["wpop_census_ratio"].max()),
            "below_0_5": int((agg["wpop_census_ratio"] < 0.5).sum()),
            "above_2_0": int((agg["wpop_census_ratio"] > 2.0).sum()),
        },
        "tokyo23_wpop_sum": wpop23,
        "tokyo23_census_total": census23,
        "tokyo23_relative_difference": (wpop23 - census23) / census23,
    }
    (OUTPUT / "worldpop-assignment.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
