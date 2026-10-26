"""Climate normals (1991-2020) per 100 m cell from the KSJ G02 mesh (third mesh, about 1 km): the value of the
third mesh that holds the cell centre.

Columns kept (scaled to their units; the file holds tenths except snow depth, in cm):
    t_year (G02_053, C), t_jan (G02_017), t_aug (G02_038), snow_max (G02_058, cm), precip_year (G02_014, mm),
    sun_year (G02_071, hours), rad_year (G02_084, MJ m-2, annual mean of the monthly daily totals)

Usage:
    uvx --with numpy --with pandas --with pyarrow python g02_features.py KSJ_DIR ART_DIR OUT.npz
"""

import glob
import json
import os
import sys
import zipfile

import numpy as np

FIELDS = {"t_year": ("G02_053", 0.1), "t_jan": ("G02_017", 0.1), "t_aug": ("G02_038", 0.1), "snow_max": ("G02_058", 1.0),
          "precip_year": ("G02_014", 0.1), "sun_year": ("G02_071", 0.1), "rad_year": ("G02_084", 0.1)}


def mesh3(lat, lon):
    lat15 = np.asarray(lat) * 1.5
    p = np.floor(lat15).astype(int)
    lo = np.asarray(lon) - 100.0
    u = np.floor(lo).astype(int)
    q = np.floor((lat15 - p) * 8).astype(int)
    v = np.floor((lo - u) * 8).astype(int)
    r = np.floor(((lat15 - p) * 8 - q) * 10).astype(int)
    w = np.floor(((lo - u) * 8 - v) * 10).astype(int)
    return np.array([f"{a:02d}{b:02d}{c}{d}{e}{f}" for a, b, c, d, e, f in zip(p, u, q, v, r, w)])


def scaled(props):
    return {k: round(props[f] * s, 6) for k, (f, s) in FIELDS.items()}


def load_normals(ksj_dir):
    table = {}
    for z in sorted(glob.glob(os.path.join(ksj_dir, "G02-22_*_GML.zip"))):
        with zipfile.ZipFile(z) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".geojson"))
            for f in json.loads(zf.read(name))["features"]:
                p = f["properties"]
                table[str(p["G02_001"])] = scaled(p)
    return table


def main():
    import pandas as pd

    ksj, art, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    table = load_normals(ksj)
    cells = pd.read_parquet(f"{art}/cells.parquet", columns=["ix", "iy", "lon", "lat"])
    meta = json.load(open(f"{art}/grid.json"))
    codes = mesh3(cells.lat.to_numpy(), cells.lon.to_numpy())
    hit = np.array([c in table for c in codes])
    print(f"{art}: {len(table)} third meshes read; cells {len(cells)}, without a normal {int((~hit).sum())}")
    out = {}
    for k in FIELDS:
        arr = np.full((meta["ny"], meta["nx"]), np.nan, dtype=np.float32)
        vals = np.array([table[c][k] if h else np.nan for c, h in zip(codes, hit)], dtype=np.float32)
        arr[cells.iy.to_numpy(), cells.ix.to_numpy()] = vals
        out[k] = arr
        print(f"  {k}: median {np.nanmedian(vals):.1f}, p10 {np.nanpercentile(vals, 10):.1f}, p90 {np.nanpercentile(vals, 90):.1f}")
    np.savez_compressed(out_path, **out)


if __name__ == "__main__":
    main()
