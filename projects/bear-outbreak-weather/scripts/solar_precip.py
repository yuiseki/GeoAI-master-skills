"""Daily solar radiation (AGERA5-SRF, J m-2 day-1) and monthly precipitation (AGERA5-PF-M, mm day-1 as a monthly
mean of the daily flux) averaged over the 0.1 degree pixels whose centre lies in each prefecture, June to August.

Each file is opened once and the four prefecture windows read. Results are appended to OUT.csv as they come, and
files already in it are skipped, so a stopped run can be resumed. NoData (-9999) pixels are left out and counted.

Usage:
    uvx --from 'duckdb>=1.5.5' --with rasterio --with numpy --with shapely --with pandas python solar_precip.py FILES.csv OUT.csv [--workers 8]
"""

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
PREFS = {"akita": "05", "gifu": "21", "kyoto": "26", "ishikawa": "17"}


def prefecture_polygons():
    import duckdb
    import shapely

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    out = {}
    for name, code in PREFS.items():
        w = con.execute(f"""SELECT ST_AsWKB(ST_Union_Agg(ST_GeomFromWKB(ST_AsWKB(geometry)))) FROM read_parquet('{ADMIN}')
                            WHERE pref_code = '{code}' AND ward IS NULL AND geometry IS NOT NULL""").fetchone()[0]
        out[name] = shapely.from_wkb(bytes(w))
    return out


def window_masks(polys, transform):
    """For each prefecture: (row0, col0, nrows, ncols, mask of pixel centres inside)."""
    import shapely

    res = {}
    for name, p in polys.items():
        minx, miny, maxx, maxy = p.bounds
        c0 = int(np.floor((minx - transform.c) / transform.a))
        c1 = int(np.ceil((maxx - transform.c) / transform.a))
        r0 = int(np.floor((maxy - transform.f) / transform.e))
        r1 = int(np.ceil((miny - transform.f) / transform.e))
        xs = transform.c + (np.arange(c0, c1) + 0.5) * transform.a
        ys = transform.f + (np.arange(r0, r1) + 0.5) * transform.e
        X, Y = np.meshgrid(xs, ys)
        res[name] = (r0, c0, r1 - r0, c1 - c0, shapely.contains_xy(p, X, Y))
    return res


def read_file(url, masks_holder, polys):
    import rasterio
    from rasterio.windows import Window

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2"):
        with rasterio.open(url) as s:
            if "m" not in masks_holder:
                masks_holder["m"] = window_masks(polys, s.transform)
            out = {}
            for name, (r0, c0, nr, nc, mask) in masks_holder["m"].items():
                a = s.read(1, window=Window(c0, r0, nc, nr)).astype(float)
                v = a[mask & (a != s.nodata)]
                out[name] = (float(v.mean()) if len(v) else float("nan"), int(len(v)), int(mask.sum()))
            return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files")
    ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    files = pd.read_csv(a.files)
    done = set(pd.read_csv(a.out).url) if os.path.exists(a.out) else set()
    todo = files[~files.url.isin(done)]
    print(f"{len(files)} files, {len(done)} done, {len(todo)} to read")
    polys = prefecture_polygons()
    holder = {}
    read_file(todo.url.iloc[0], holder, polys) if len(todo) else None  # fix the window masks once
    new = not os.path.exists(a.out)
    with open(a.out, "a") as fh, ThreadPoolExecutor(max_workers=a.workers) as ex:
        if new:
            fh.write("short_id,date,url,region,value,valid,pixels\n")
        futs = {ex.submit(read_file, r.url, holder, polys): r for r in todo.itertuples()}
        for k, f in enumerate(as_completed(futs)):
            r = futs[f]
            for name, (v, n, px) in f.result().items():
                fh.write(f"{r.short_id},{r.start_datetime[:10]},{r.url},{name},{v},{n},{px}\n")
            fh.flush()
            if k % 100 == 0:
                print(k, "files", flush=True)
    print("done")


if __name__ == "__main__":
    main()
