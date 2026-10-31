"""April-September report counts per 100 m cell for bear years 2023-2026, and one row per report for the
reporting-process diagnostics, from the fixed Akita Kumadas snapshot.

The season is the same for every year (1 April to 30 September) because bear year 2026 ends there. The full-year
counts rebuilt from the same points must equal the saved reports_by_year.npz (seasonal_labels refuses otherwise),
and the seasonal positive cells must equal those of the earlier runs (R036: 1,586, 1,132, 3,657, 3,036).

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA \
      -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy --with pandas --with pyarrow \
      --with pyproj python projects/_bear/akita-bear-human-interface/scripts/interface_labels.py \
      artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-human-interface/labels \
      projects/_bear/akita-bear-human-interface/outputs/labels_check.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

import labels as lb
from grid import Grid
from seasonal_report_composition import _info_type, assign_municipality
from seasonal_transfer_b_env import seasonal_labels

YEARS = (2023, 2024, 2025, 2026)
KNOWN_SEASON_POSITIVES = {2023: 1586, 2024: 1132, 2025: 3657, 2026: 3036}


def main():
    import duckdb
    import pandas as pd
    import pyproj

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("outdir", type=Path)
    a.add_argument("check", type=Path)
    args = a.parse_args()
    meta = json.loads((args.art / "grid.json").read_text(encoding="utf-8"))
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    muni = np.load(args.art / "grid_mask.npz")["muni"]
    inside = muni >= 0
    cells = pd.read_parquet(args.art / "cells.parquet", columns=["ix", "iy"])
    iy, ix = np.nonzero(inside)
    if not (np.array_equal(cells.ix.to_numpy(), ix) and np.array_equal(cells.iy.to_numpy(), iy)):
        raise ValueError("cells.parquet is not in the row-major order of the prefecture mask")
    with np.load(args.art / "reports_by_year.npz") as saved:
        known = {y: saved[f"c{y}"] for y in YEARS}
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at, info_type FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ?""", [lb.SIGHTING, "ツキノワグマ", "2023-04-01"]).fetchnumpy()
    tr = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = tr.transform(raw["longitude"], raw["latitude"])
    season, info = seasonal_labels(grid, muni, x, y, raw["observed_at"], known, years=YEARS)
    for yr in YEARS:
        if info[yr]["positive_cells"] != KNOWN_SEASON_POSITIVES[yr]:
            raise ValueError(f"{yr}: {info[yr]['positive_cells']} seasonal positive cells, expected {KNOWN_SEASON_POSITIVES[yr]}")
    dates = np.asarray(raw["observed_at"], dtype="datetime64[m]")
    fy = lb.bear_year(dates)
    month = dates.astype("datetime64[M]").astype(int) % 12 + 1
    assigned = assign_municipality(grid, muni, x, y)
    gx, gy, ok = grid.index(x, y)
    flat = np.full(grid.ny * grid.nx, -1, dtype=np.int64)
    flat[(iy * grid.nx + ix)] = np.arange(len(ix))
    cell = np.where(ok, flat[np.where(ok, gy * grid.nx + gx, 0)], -1)
    cell[assigned < 0] = -1
    keep = np.isin(fy, YEARS)
    rows = pd.DataFrame({"bear_year": fy[keep], "in_season": ((month >= 4) & (month <= 9))[keep],
                         "cell": cell[keep], "muni": assigned[keep],
                         "info_type": [_info_type(None if np.ma.is_masked(v) else v) for v in raw["info_type"][keep]]})
    for yr in YEARS:  # the rows rebuild the counts
        r = rows[(rows.bear_year == yr) & rows.in_season & (rows.cell >= 0)]
        if not np.array_equal(np.bincount(r.cell, minlength=len(ix)), season[yr][inside]):
            raise ValueError(f"{yr}: report rows do not rebuild the seasonal counts")
    args.outdir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.outdir / "season_counts.npz", **{f"s{yr}": season[yr].astype(np.int32) for yr in YEARS})
    rows.to_parquet(args.outdir / "reports.parquet", index=False)
    out = {"derived": "counts of observed reports per fixed cell; not a model output",
           "source": lb.SIGHTING, "season": "1 April to 30 September of each bear year", "labels": {str(k): v for k, v in info.items()},
           "rows": int(len(rows)), "rows_outside_prefecture": int((rows.cell < 0).sum())}
    args.check.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.check, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
