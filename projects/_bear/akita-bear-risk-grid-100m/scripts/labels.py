"""Bear reports per 100 m cell and bear year (April to March), from the Akita Kumadas points.

All kinds of bear report count (sighting, traces, damage, injury). A point goes to the cell its location
falls in; points outside the prefecture's cells (the sea, the neighbouring prefectures) are counted per
year and left out. Writes `reports_by_year.npz` with `c2022` ... `c2026` ([ny, nx] counts) and prints the
counts. Bear year 2026 covers April to September 2026 only (the data end on 2026-09-30).

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy \
        --with pyproj python labels.py ART_DIR [--info-type 目撃 --out-name reports_by_year_sight.npz]
"""

import json
import sys

import numpy as np

from grid import CRS, Grid

SIGHTING = "hf://datasets/yuiseki/akita-kumadas-wildlife-sighting@c7047ab442ea3471aaa52af6e56a966ac768ff61/parquet/sighting.parquet"
YEARS = [2022, 2023, 2024, 2025, 2026]


def bear_year(ts):
    ts = np.asarray(ts, dtype="datetime64[m]")
    y = ts.astype("datetime64[Y]").astype(int) + 1970
    m = ts.astype("datetime64[M]").astype(int) % 12 + 1
    return np.where(m >= 4, y, y - 1)


def counts_by_year(grid, muni, x, y, years, wanted):
    ix, iy, ok = grid.index(x, y)
    inside = np.zeros(len(ix), dtype=bool)
    inside[ok] = muni[iy[ok], ix[ok]] >= 0
    counts, off = {}, {}
    for yr in wanted:
        sel = years == yr
        counts[yr], _ = grid.sum_into(np.asarray(x)[sel & inside], np.asarray(y)[sel & inside])
        off[yr] = int((sel & ~inside).sum())
    return counts, off


def main():
    import duckdb
    import pyproj

    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("art")
    ap.add_argument("--info-type", default=None, help="only this kind of report (e.g. 目撃); default: every kind")
    ap.add_argument("--out-name", default="reports_by_year.npz")
    a = ap.parse_args()
    art = a.art
    meta = json.load(open(f"{art}/grid.json"))
    g = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    muni = np.load(f"{art}/grid_mask.npz")["muni"]
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    kind = "" if a.info_type is None else " AND info_type = ?"
    d = con.execute(f"SELECT longitude, latitude, observed_at FROM '{SIGHTING}' WHERE species = 'ツキノワグマ'{kind}",
                    [] if a.info_type is None else [a.info_type]).fetchnumpy()
    tr = pyproj.Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    x, y = tr.transform(d["longitude"], d["latitude"])
    yrs = bear_year(d["observed_at"].astype("datetime64[m]"))
    print("bear reports:", len(x), "| by bear year:", {int(k): int(v) for k, v in zip(*np.unique(yrs, return_counts=True))})
    counts, off = counts_by_year(g, muni, x, y, yrs, YEARS)
    inside = muni >= 0
    for yr in YEARS:
        c = counts[yr]
        print(f"  {yr}: reports in prefecture cells {int(c[inside].sum())}, outside {off[yr]}, "
              f"cells with >= 1 report {int((c[inside] > 0).sum())} ({(c[inside] > 0).mean():.4%} of cells)")
    np.savez_compressed(f"{art}/{a.out_name}", **{f"c{yr}": counts[yr].astype(np.int32) for yr in YEARS})
    print("wrote", a.out_name)


if __name__ == "__main__":
    main()
