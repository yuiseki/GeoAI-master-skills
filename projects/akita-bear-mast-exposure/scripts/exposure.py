"""Beech and oak exposure of each 100 m cell: the share of the mapped area within 500 m and 2 km that the
category's vegetation polygons cover.

The polygons (現存植生図2024, Akita, fixed revision) are moved to EPSG:6678 and burned into 10 m pixels aligned with
the 100 m grid of akita-bear-risk-grid-100m (a pixel is in when its centre is in a polygon). Each category is
burned on its own, so overlapping polygons are not counted twice; beech_oak burns the four categories together
(their union). All polygons together give the mapped area (Akita as the vegetation map covers it), which is the
denominator. Disk: the cells whose centres are within the radius of the cell's centre.

Writes ART/exposure.npz ([ny, nx] arrays, row 0 = south) and OUT_JSON (counts and checks).

    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy \
      --with scipy --with shapely --with pyproj --with rasterio python exposure.py BEAR_ART MAPPING_CSV ART OUT_JSON
"""

import csv
import hashlib
import json
import sys
from dataclasses import dataclass

import numpy as np

VEG = ("hf://datasets/yuiseki/akita-vegetation-2024@b3b36a0fb6ff027fb1f483be3288df2df76c0cf3/"
       "parquet/vegetation_akita.parquet")
CATS = ("beech", "beech_mizunara", "mizunara", "konara")
RADII = {"500": 5, "2000": 20}  # metres: cells
FINE = 10  # pixels per 100 m cell side


@dataclass(frozen=True)
class Grid:
    x0: float
    y0: float
    nx: int
    ny: int
    size: float = 100.0


def burn(geoms, g):
    """uint8 [ny*FINE, nx*FINE] with row 0 = south: 1 where a pixel centre is inside any of the geometries."""
    from affine import Affine
    from rasterio.features import rasterize

    res = g.size / FINE
    shape = (g.ny * FINE, g.nx * FINE)
    t = Affine(res, 0, g.x0, 0, -res, g.y0 + g.ny * g.size)
    a = rasterize(((geom, 1) for geom in geoms), out_shape=shape, transform=t, fill=0, dtype="uint8", all_touched=False)
    return a[::-1]


def cell_counts(fine):
    ny, nx = fine.shape[0] // FINE, fine.shape[1] // FINE
    return fine.reshape(ny, FINE, nx, FINE).sum(axis=(1, 3), dtype=np.int32)


def disk(r):
    d = np.arange(-r, r + 1)
    return (d[:, None] ** 2 + d[None, :] ** 2) <= r * r


def disk_sum(a, k):
    from scipy.signal import fftconvolve

    return np.rint(fftconvolve(a, k.astype(float), mode="same"))


def disk_fraction(cat, anyv, r):
    k = disk(r)
    num, den = disk_sum(cat, k), disk_sum(anyv, k)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_polygons(codes_by_cat):
    """{name: [shapely geometries in EPSG:6678]} for each category and 'any' (all polygons)."""
    import duckdb
    import shapely
    from pyproj import Transformer

    con = duckdb.connect()
    con.sql("LOAD spatial")
    rows = con.sql(f"SELECT 凡例コード, ST_AsWKB(geometry) FROM '{VEG}'").fetchall()
    geoms = shapely.from_wkb([bytes(r[1]) for r in rows])
    tr = Transformer.from_crs("EPSG:6668", "EPSG:6678", always_xy=True)
    geoms = shapely.transform(geoms, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))
    code = np.array([r[0] for r in rows])
    out = {"any": list(geoms)}
    for cat, codes in codes_by_cat.items():
        out[cat] = list(geoms[np.isin(code, list(codes))])
    out["beech_oak"] = [x for c in CATS for x in out[c]]
    return out, len(rows), float(shapely.area(geoms).sum())


def main():
    bear, mapping_csv, art, out_json = sys.argv[1:5]
    gj = json.load(open(f"{bear}/grid.json"))
    g = Grid(gj["x0"], gj["y0"], gj["nx"], gj["ny"], gj["size"])
    muni = np.load(f"{bear}/grid_mask.npz")["muni"]
    inside = muni >= 0
    codes = {c: set() for c in CATS}
    for r in csv.DictReader(open(mapping_csv, encoding="utf-8")):
        if r["category"] in codes:
            codes[r["category"]].add(r["凡例コード"])
    polys, n_poly, area_6678 = load_polygons(codes)
    counts = {}
    for name in ("any", *CATS, "beech_oak"):
        counts[name] = cell_counts(burn(polys[name], g))
        print(name, len(polys[name]), int(counts[name].sum()), flush=True)
    arrays = {f"cell_{n}": c.astype(np.uint8) for n, c in counts.items()}
    for rname, rc in RADII.items():
        for n in (*CATS, "beech_oak"):
            arrays[f"{n}_fraction_{rname}"] = disk_fraction(counts[n].astype(float), counts["any"].astype(float), rc).astype(np.float32)
    np.savez_compressed(f"{art}/exposure.npz", **arrays)
    px = (g.size / FINE) ** 2 / 1e6  # km2 per pixel
    res = {
        "vegetation": VEG, "polygons": n_poly, "polygon_area_km2_epsg6678": area_6678 / 1e6,
        "mapping_csv_sha256": sha256(mapping_csv), "grid": gj | {"codes": None, "names": None},
        "pixel_m": g.size / FINE, "radii_m": [500, 2000],
        "polygons_by_category": {n: len(polys[n]) for n in ("any", *CATS, "beech_oak")},
        "burned_area_km2": {n: int(c.sum()) * px for n, c in counts.items()},
        "burned_area_in_prefecture_cells_km2": {n: int(c[inside].sum()) * px for n, c in counts.items()},
        "sum_of_categories_minus_union_km2": (sum(int(counts[c].sum()) for c in CATS) - int(counts["beech_oak"].sum())) * px,
        "prefecture_cells": int(inside.sum()),
        "prefecture_cells_without_mapped_area": int((counts["any"][inside] == 0).sum()),
        "nan_fraction_in_prefecture_cells": {k: int(np.isnan(v[inside]).sum()) for k, v in arrays.items() if "fraction" in k},
        "exposure_npz_sha256": sha256(f"{art}/exposure.npz"),
    }
    json.dump(res, open(out_json, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
