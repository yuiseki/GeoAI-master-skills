"""Fixed Apr–Sep municipal and info_type composition audit; no model fitting.

From repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy \
      --with scikit-learn==1.9.1 --with pyproj python \
      projects/_bear/akita-bear-risk-grid-100m/scripts/seasonal_report_composition.py \
      /Workspaces/tmp/_exp/GeoAI-bear/GeoAI-master-skills/artifacts/_bear/akita-bear-risk-grid-100m \
      projects/_bear/akita-bear-risk-grid-100m/outputs/apr_sep_report_composition.json
"""

import argparse
import json
from pathlib import Path

import numpy as np
import scipy
from scipy.spatial.distance import jensenshannon

from grid import Grid
import labels as lb
import same_year_spatial_oof as spatial
from seasonal_transfer_b_env import seasonal_labels

YEARS = (2024, 2025, 2026)
PAIRS = ((2024, 2025), (2025, 2026))
MISSING_INFO_TYPE = "(欠損)"
LABEL_KEYS = ("positive_cells", "inside_window_reports", "outside_window_reports")


def js_divergence(earlier, later):
    """Jensen–Shannon divergence in bits, not Jensen–Shannon distance."""
    a, b = np.asarray(earlier, dtype=float), np.asarray(later, dtype=float)
    if a.ndim != 1 or b.shape != a.shape or not np.isfinite(a).all() or not np.isfinite(b).all() \
            or np.any(a < 0) or np.any(b < 0) or a.sum() <= 0 or b.sum() <= 0:
        raise ValueError("comparable nonnegative vectors with positive totals required")
    return float(jensenshannon(a, b, base=2.0) ** 2)


def assign_municipality(grid, muni, x, y):
    x, y = np.asarray(x), np.asarray(y)
    if x.shape != y.shape or x.ndim != 1 or muni.shape != (grid.ny, grid.nx):
        raise ValueError("grid, coordinates and municipality mask must align")
    ix, iy, valid = grid.index(x, y)
    assigned = np.full(len(x), -1, dtype=np.int16)
    assigned[valid] = muni[iy[valid], ix[valid]]
    return assigned


def _info_type(value):
    if value is None or value is np.ma.masked or (isinstance(value, float) and np.isnan(value)) \
            or value == "":
        return MISSING_INFO_TYPE
    return str(value)


def summarize_year(muni, cell_counts, report_muni, info_types, codes, names):
    """Count reports and distinct positive cells in the same grid-assigned municipality."""
    muni, cell_counts, report_muni = map(np.asarray, (muni, cell_counts, report_muni))
    info_types = list(info_types)
    if muni.ndim != 2 or cell_counts.shape != muni.shape or report_muni.shape != (len(info_types),) \
            or len(codes) != len(names) or np.any((report_muni < 0) | (report_muni >= len(codes))) \
            or np.any((muni >= len(codes)) | (muni < -1)):
        raise ValueError("municipal reports, cells and metadata must align")
    if not np.isfinite(cell_counts).all() or np.any(cell_counts < 0) \
            or not np.array_equal(cell_counts, np.floor(cell_counts)):
        raise ValueError("cell counts must be finite nonnegative integers")
    n_reports = len(report_muni)
    n_cells = int(np.count_nonzero((cell_counts > 0) & (muni >= 0)))
    if int(cell_counts[muni >= 0].sum()) != n_reports or n_reports == 0 or n_cells == 0:
        raise ValueError("report counts and positive cells do not reconcile")
    rows = []
    for i, (code, name) in enumerate(zip(codes, names)):
        rc = int(np.count_nonzero(report_muni == i))
        pc = int(np.count_nonzero((cell_counts > 0) & (muni == i)))
        rows.append({"code5": code, "name": name, "report_count": rc,
                     "report_share": rc / n_reports, "positive_cell_count": pc,
                     "positive_cell_share": pc / n_cells})
    if sum(row["report_count"] for row in rows) != n_reports \
            or sum(row["positive_cell_count"] for row in rows) != n_cells:
        raise ValueError("municipal sums do not equal prefecture totals")
    type_counts = {}
    for value in info_types:
        key = _info_type(value)
        type_counts[key] = type_counts.get(key, 0) + 1
    types = {key: {"count": count, "share": count / n_reports}
             for key, count in sorted(type_counts.items())}
    return {"n_reports": n_reports, "n_positive_cells": n_cells,
            "municipalities": rows, "info_types": types}


def compare_counts(earlier, later, *, top_n):
    keys = sorted(set(earlier) | set(later))
    a = np.array([earlier.get(key, 0) for key in keys], dtype=float)
    b = np.array([later.get(key, 0) for key in keys], dtype=float)
    divergence = js_divergence(a, b)
    pa, pb = a / a.sum(), b / b.sum()
    rows = [{"category": key, "earlier_share": float(pa[i]), "later_share": float(pb[i]),
             "change_percentage_points": float((pb[i] - pa[i]) * 100),
             "absolute_change_percentage_points": float(abs(pb[i] - pa[i]) * 100)}
            for i, key in enumerate(keys)]
    rows.sort(key=lambda row: (-row["absolute_change_percentage_points"], row["category"]))
    return {"js_divergence_bits": divergence,
            "largest_share_changes": rows[:top_n], "n_categories": len(keys)}


def _municipal_counts(rows, field):
    return {row["code5"]: row[field] for row in rows}


def main():
    import duckdb
    import pyproj

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("art", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("output already exists; refusing post-result replacement")
    project = Path(__file__).resolve().parents[1]
    previous_path = project / "outputs/apr_sep_year_transfer_b_env.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    if previous["setup"]["source"] != lb.SIGHTING:
        raise ValueError("fixed sighting source changed")
    fixed_files = ("grid_mask.npz", "reports_by_year.npz", "cells.parquet",
                   "worldcover.npz", "dem.npz", "worldpop.npz", "osm.npz")
    hashes = {name: spatial.sha256(args.art / name) for name in fixed_files}
    if hashes != previous["setup"]["fixed_input_sha256"]:
        raise ValueError("fixed input artifacts changed")
    grid_path = args.art / "grid.json"
    meta = json.loads(grid_path.read_text(encoding="utf-8"))
    if spatial.sha256(grid_path) != previous["setup"]["grid_json_sha256"] \
            or meta["crs"] != "EPSG:6678" or meta["size"] != 100 \
            or len(meta["codes"]) != len(meta["names"]):
        raise ValueError("fixed municipality grid changed")
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(args.art / "grid_mask.npz") as masked:
        muni = masked["muni"]
    if muni.shape != (grid.ny, grid.nx) or int((muni >= 0).sum()) != previous["setup"]["n_cells"]:
        raise ValueError("prefecture cell mask differs")
    with np.load(args.art / "reports_by_year.npz") as saved:
        known = {year: saved[f"c{year}"] for year in YEARS}
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at, info_type
                         FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2024-04-01", "2026-10-01"]).fetchnumpy()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = transformer.transform(raw["longitude"], raw["latitude"])
    counts, label_info = seasonal_labels(grid, muni, x, y, raw["observed_at"], known, years=YEARS)
    for year in YEARS:
        for key in LABEL_KEYS:
            if label_info[year][key] != previous["labels"][str(year)][key]:
                raise ValueError(f"{year} {key} does not reproduce previous seasonal labels")
    assigned = assign_municipality(grid, muni, x, y)
    dates = np.asarray(raw["observed_at"], dtype="datetime64[m]")
    info_values = raw["info_type"]
    results = {}
    for year in YEARS:
        chosen = (dates >= np.datetime64(f"{year}-04-01")) & (dates < np.datetime64(f"{year}-10-01"))
        inside = chosen & (assigned >= 0)
        if int(np.count_nonzero(chosen & (assigned < 0))) != label_info[year]["outside_window_reports"]:
            raise ValueError(f"{year} off-prefecture count differs from saved labels")
        values = [None if np.ma.is_masked(info_values[i]) else info_values[i] for i in np.flatnonzero(inside)]
        result = summarize_year(muni, counts[year], assigned[inside], values, meta["codes"], meta["names"])
        if result["n_reports"] != label_info[year]["inside_window_reports"] \
                or result["n_positive_cells"] != label_info[year]["positive_cells"]:
            raise ValueError(f"{year} municipal or type totals differ from seasonal labels")
        results[str(year)] = {"window_start_inclusive": label_info[year]["window_start_inclusive"],
                              "window_end_exclusive": label_info[year]["window_end_exclusive"],
                              "n_source_window_reports": int(chosen.sum()),
                              "n_outside_prefecture": label_info[year]["outside_window_reports"], **result}
        print(year, "reports", result["n_reports"], "positive cells", result["n_positive_cells"],
              "info_types", result["info_types"], flush=True)
    all_types = sorted({key for row in results.values() for key in row["info_types"]})
    for row in results.values():
        row["info_types"] = {key: row["info_types"].get(key, {"count": 0, "share": 0.0})
                             for key in all_types}
    comparisons = {}
    for earlier, later in PAIRS:
        a, b = results[str(earlier)], results[str(later)]
        key = f"{earlier}_to_{later}"
        comparisons[key] = {
            "municipal_report_count": compare_counts(_municipal_counts(a["municipalities"], "report_count"),
                                                       _municipal_counts(b["municipalities"], "report_count"), top_n=5),
            "municipal_positive_cell_count": compare_counts(_municipal_counts(a["municipalities"], "positive_cell_count"),
                                                              _municipal_counts(b["municipalities"], "positive_cell_count"), top_n=5),
            "info_type_count": compare_counts({name: value["count"] for name, value in a["info_types"].items()},
                                               {name: value["count"] for name, value in b["info_types"].items()},
                                               top_n=len(all_types))}
    name_by_code = dict(zip(meta["codes"], meta["names"]))
    for comparison in comparisons.values():
        for field in ("municipal_report_count", "municipal_positive_cell_count"):
            for row in comparison[field]["largest_share_changes"]:
                row["name"] = name_by_code[row["category"]]
    output = {"mode": "exploratory descriptive composition audit; no fitting",
              "definition": {"source": lb.SIGHTING, "species": "ツキノワグマ", "info_type": "source category, NULL/empty as (欠損)",
                             "municipality": "existing 100m cell-centre label from grid_mask.npz, not source municipality string",
                             "population": "reports in prefecture grid cells only; outside reports listed separately",
                             "positive_cell": "one or more Apr–Sep reports in fixed 100m cell",
                             "share_denominator": "prefecture-inside report count or distinct positive-cell count in that year",
                             "js_divergence": "Jensen–Shannon distance squared with base 2 (bits), 0 identical, 1 disjoint",
                             "top_change": "absolute later-minus-earlier share, in percentage points"},
              "setup": {"fixed_input_sha256": hashes, "grid_json_sha256": spatial.sha256(grid_path),
                        "previous_transfer_json_sha256": spatial.sha256(previous_path),
                        "numpy_version": np.__version__, "scipy_version": scipy.__version__,
                        "script": "projects/_bear/akita-bear-risk-grid-100m/scripts/seasonal_report_composition.py"},
              "years": results, "comparisons": comparisons,
              "limitations": ["grid-based municipality assignment may differ from the source municipality text near boundaries",
                              "info_type and municipal composition may change because of bear behaviour as well as observation/reporting process",
                              "composition shift alone does not identify reporting bias or the cause of model performance change"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JSD bits:", {name: {field: row["js_divergence_bits"] for field, row in fields.items()}
                        for name, fields in comparisons.items()}, flush=True)


if __name__ == "__main__":
    main()
