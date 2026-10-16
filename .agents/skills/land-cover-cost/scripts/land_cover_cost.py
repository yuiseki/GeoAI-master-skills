"""Turn a categorical land-cover raster into a cost raster (cost of one metre) with an explicit table.

The mapping table is a CSV with at least the columns class, status and cost_per_m (any other column,
such as source or note, is carried into the audit):

    class      an integer class code of the raster
    status     passable or barrier
    cost_per_m for passable classes, the cost of moving one metre (a positive finite number in
               --cost-unit); empty for barriers

The run stops, before writing anything, on: a class in the raster that the table does not list, a
class listed twice, a passable class without a positive finite cost, a barrier with a cost, a status
other than the two, a non-integer class or raster, or a listed class equal to the raster's NoData
value. Classes listed but absent from the raster are allowed and counted as 0.

Output: a float64 GeoTIFF on the same grid (CRS, transform, width, height), NoData NaN:
    passable cells   the class's cost per metre
    barrier cells    --barrier-value (default -1; any value that cannot be a cost: <= 0 or inf)
    NoData cells     NaN (the input's NoData cells, and only those)
and an audit JSON (--audit, default OUT with .audit.json): input, mapping, its SHA-256, cost unit,
barrier value, each class with its row of the table and its cell count, the counts of passable,
barrier and NoData cells, the grid, and the output path.

The raster is read block by block twice: once to count the classes (and stop on unmapped ones),
once to write.

Usage:
    uvx --with numpy --with rasterio python land_cover_cost.py LANDCOVER.tif MAPPING.csv \\
        --cost-unit s/m --out COST.tif [--barrier-value -1] [--audit COST.audit.json] [--band 1]
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

REQUIRED = ("class", "status", "cost_per_m")


def read_mapping(path):
    """{class: row} from the CSV, with cost_per_m parsed; stops on any row that breaks the schema."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path} lacks the columns {missing}; it needs {list(REQUIRED)}")
        rows = list(reader)
    out, problems = {}, []
    for n, row in enumerate(rows, 2):
        raw = row["class"].strip()
        try:
            k = int(raw)
        except ValueError:
            problems.append(f"line {n}: class {raw!r} is not an integer")
            continue
        if k in out:
            problems.append(f"line {n}: class {k} is listed more than once")
            continue
        status, cost = row["status"].strip(), row["cost_per_m"].strip()
        if status == "passable":
            try:
                v = float(cost)
            except ValueError:
                problems.append(f"line {n}: class {k} is passable but cost_per_m {cost!r} is not a number")
                continue
            if not (math.isfinite(v) and v > 0):
                problems.append(f"line {n}: class {k} is passable but cost_per_m {cost} is not positive and finite")
                continue
        elif status == "barrier":
            if cost:
                problems.append(f"line {n}: class {k} is a barrier but has cost_per_m {cost}; leave it empty")
                continue
            v = None
        else:
            problems.append(f"line {n}: class {k} has status {status!r}; use passable or barrier")
            continue
        out[k] = {**{c: (row[c] or "").strip() for c in row if c is not None}, "class": k, "status": status,
                  "cost_per_m": v}
    if problems:
        raise SystemExit(f"{path}: " + "; ".join(problems))
    if not out:
        raise SystemExit(f"{path} has no classes")
    return out


def _barrier(value):
    v = float(value)
    if math.isnan(v) or (math.isfinite(v) and v > 0):
        raise SystemExit(f"--barrier-value {value} could be read as a cost; use a value <= 0 or inf")
    return v


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def convert(raster, mapping, out, cost_unit, barrier_value="-1", audit_path=None, band=1):
    """Write the cost raster and the audit; returns the audit as a dict."""
    import rasterio

    if not cost_unit.endswith("/m") or cost_unit == "/m":
        raise SystemExit(f"--cost-unit {cost_unit!r} must be a cost per metre, such as s/m")
    bv = _barrier(barrier_value)
    table = read_mapping(mapping)
    audit_path = audit_path or str(Path(out).with_suffix(".audit.json"))
    for p in (out, audit_path):
        if Path(p).exists():
            raise SystemExit(f"{p} exists; remove it or choose another path")

    classes = np.array(sorted(table), dtype=np.int64)
    costs = np.array([bv if table[k]["status"] == "barrier" else table[k]["cost_per_m"] for k in classes])
    with rasterio.open(raster) as src:
        dtype = np.dtype(src.dtypes[band - 1])
        if not np.issubdtype(dtype, np.integer):
            raise SystemExit(f"{raster} band {band} is {dtype}; a categorical raster has an integer type")
        nd = src.nodatavals[band - 1]
        if nd is not None and float(nd) in table:
            raise SystemExit(f"class {int(nd)} is in the mapping but is the raster's NoData value")
        windows = [w for _, w in src.block_windows(band)]

        counts, nodata = {}, 0
        for w in windows:
            a = src.read(band, window=w)
            valid = np.ones(a.shape, bool) if nd is None else a != nd
            nodata += int((~valid).sum())
            vals, n = np.unique(a[valid], return_counts=True)
            for v, c in zip(vals.tolist(), n.tolist()):
                counts[v] = counts.get(v, 0) + c
        unmapped = {k: v for k, v in counts.items() if k not in table}
        if unmapped:
            raise SystemExit(f"{len(unmapped)} classes of the raster are not in the mapping (class: cells): "
                             f"{dict(sorted(unmapped.items()))}")

        profile = {k: v for k, v in src.profile.items() if k not in ("predictor", "photometric")}
        profile.update(count=1, dtype="float64", nodata=float("nan"), compress="deflate")
        written = {"passable": 0, "barrier": 0, "nodata": 0}
        with rasterio.open(out, "w", **profile) as dst:
            for w in windows:
                a = src.read(band, window=w)
                valid = np.ones(a.shape, bool) if nd is None else a != nd
                idx = np.searchsorted(classes, a)
                v = np.full(a.shape, np.nan)
                v[valid] = costs[idx[valid]]
                dst.write(v, 1, window=w)
                written["nodata"] += int((~valid).sum())
                written["barrier"] += int((valid & (v == bv)).sum()) if not math.isinf(bv) else int(
                    (valid & np.isinf(v)).sum())
                written["passable"] += int((valid & (v > 0) & np.isfinite(v)).sum())
        grid = {"crs": src.crs.to_string() if src.crs else None, "transform": list(src.transform)[:6],
                "width": src.width, "height": src.height, "res": list(src.res)}

    total = grid["width"] * grid["height"]
    expected = {"passable": sum(c for k, c in counts.items() if table[k]["status"] == "passable"),
                "barrier": sum(c for k, c in counts.items() if table[k]["status"] == "barrier"), "nodata": nodata}
    if written != expected or sum(written.values()) != total:
        Path(out).unlink()
        raise SystemExit(f"written cells {written} do not match the counted {expected} of {total}; removed {out}")

    audit = {
        "input": str(raster), "band": band, "mapping": str(mapping), "mapping_sha256": _sha256(mapping),
        "cost_unit": cost_unit, "barrier_value": "inf" if math.isinf(bv) else bv, "nodata": "NaN",
        "classes": [{**{k: v for k, v in table[k].items()}, "cells": counts.get(k, 0)} for k in classes.tolist()],
        "cells": {"total": total, **written}, "grid": grid, "output": str(out),
    }
    Path(audit_path).write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    return audit


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("raster")
    p.add_argument("mapping")
    p.add_argument("--cost-unit", required=True, help="the unit of cost_per_m, ending in /m (s/m, min/m)")
    p.add_argument("--out", required=True)
    p.add_argument("--barrier-value", default="-1")
    p.add_argument("--audit")
    p.add_argument("--band", type=int, default=1)
    a = p.parse_args()
    audit = convert(a.raster, a.mapping, a.out, a.cost_unit, a.barrier_value, a.audit, a.band)
    c = audit["cells"]
    print(f"{a.raster} -> {a.out}: {audit['grid']['width']} x {audit['grid']['height']}, CRS {audit['grid']['crs']}")
    print(f"mapping {a.mapping} (sha256 {audit['mapping_sha256'][:12]}...), cost unit {a.cost_unit}, "
          f"barrier value {audit['barrier_value']}, NoData NaN")
    print(f"cells {c['total']}: passable {c['passable']}, barrier {c['barrier']}, nodata {c['nodata']}")
    for k in audit["classes"]:
        print(f"  class {k['class']:>5} {k['status']:<8} {'' if k['cost_per_m'] is None else k['cost_per_m']:<8} "
              f"cells {k['cells']}")
    print(f"audit: {Path(a.audit or Path(a.out).with_suffix('.audit.json'))}")


if __name__ == "__main__":
    main()
