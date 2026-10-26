"""Check whether CTrees block means compare the same underlying 100m pixels.

Run: uvx --with numpy --with rasterio python projects/hokkaido-forest-biomass-survey/scripts/common_pixels.py
Downloads two fixed, public source crops into ignored artifacts and verifies SHA256.
"""

import csv
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import rasterio

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
REVISION = "e0edd7cd9812847d1740cf1b35ac84885cde3bef"
BASE = f"https://huggingface.co/datasets/yuiseki/ctrees-agb-hokkaido-east-100m/resolve/{REVISION}/source"
FILES = {
    2010: ("ctrees_agb_2010_hokkaido_east.tif", "c00b996a88af80621fda6c82d19fb38fbb1599dca8c94131733ba1cfdd5b21c6"),
    2025: ("ctrees_agb_2025_hokkaido_east.tif", "07f370a54985d7dec86c0cdc0413a4778c9959ab7b8b38bee6dce442b6fefa51"),
}


def common_block(old, new):
    if old.shape != new.shape:
        raise ValueError("raster block shape mismatch")
    old_valid = old != -9999
    new_valid = new != -9999
    common = old_valid & new_valid
    n = int(common.sum())
    return {
        "common_pixels": n,
        "mask_mismatch_pixels": int(np.logical_xor(old_valid, new_valid).sum()),
        "old_mean": float(old[common].mean()) / 10 if n else None,
        "new_mean": float(new[common].mean()) / 10 if n else None,
        "drop": float(old[common].mean() - new[common].mean()) / 10 if n else None,
    }


def download_checked(year):
    name, expected = FILES[year]
    directory = ROOT / "artifacts/hokkaido-forest-biomass-survey/source"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    if not path.is_file():
        with urlopen(f"{BASE}/{name}", timeout=60) as response, path.open("wb") as output:
            shutil.copyfileobj(response, output)
    with path.open("rb") as fh:
        digest = hashlib.file_digest(fh, "sha256").hexdigest()
    if digest != expected:
        raise RuntimeError(f"source hash mismatch for {name}: {digest}")
    return path, digest


def main():
    paths = {year: download_checked(year) for year in FILES}
    with rasterio.open(paths[2010][0]) as a, rasterio.open(paths[2025][0]) as b:
        if (a.shape != b.shape or a.transform != b.transform or
                a.crs != b.crs or a.nodata not in (None, -9999) or
                b.nodata not in (None, -9999)):
            raise RuntimeError("raw raster grids or nodata differ")
        old, new = a.read(1), b.read(1)
        raster_meta = {"shape": a.shape, "crs": str(a.crs),
                       "file_nodata_metadata": a.nodata, "used_sentinel": -9999,
                       "transform": tuple(a.transform)}
    main_summary = json.loads((PROJECT / "outputs/summary.json").read_text())
    with (PROJECT / "outputs/cell_metrics.csv").open(newline="") as fh:
        cells = list(csv.DictReader(fh))
    audited = []
    for r in cells:
        row, col = int(r["cell_row"]), int(r["cell_col"])
        i, j = row * 10, col * 10
        if i + 10 > old.shape[0] or j + 10 > old.shape[1]:
            raise RuntimeError("block outside source raster")
        result = common_block(old[i:i + 10, j:j + 10], new[i:i + 10, j:j + 10])
        result.update(cell_row=row, cell_col=col)
        result["aggregated_drop"] = float(r["drop"])
        result["delta_vs_aggregated"] = (result["drop"] - result["aggregated_drop"]
                                         if result["drop"] is not None else None)
        audited.append(result)
    eligible = {(int(r["cell_row"]), int(r["cell_col"])) for r in cells
                if float(r["cover_frac"]) >= 0.95 and float(r["forest_frac"]) >= 0.8 and
                int(r["valid_pixels_2010"]) >= 80 and int(r["valid_pixels_2025"]) >= 80}
    common_rank = sorted((r for r in audited if (r["cell_row"], r["cell_col"]) in eligible
                          and r["common_pixels"] >= 80 and r["drop"] is not None and r["drop"] > 0),
                         key=lambda r: (-r["drop"], r["cell_row"], r["cell_col"]))[:20]
    main_top = {(r["cell_row"], r["cell_col"]) for r in main_summary["main_top20"]}
    common_top = {(r["cell_row"], r["cell_col"]) for r in common_rank}
    if len(common_rank) < 20:
        raise RuntimeError("not enough common-mask candidates")
    summary = {
        "date": str(date.today()), "input_revision": REVISION,
        "raw_source_sha256": {year: digest for year, (_, digest) in paths.items()},
        "raster": raster_meta,
        "cells_audited": len(audited),
        "cells_mask_mismatch": sum(r["mask_mismatch_pixels"] > 0 for r in audited),
        "cells_no_common_pixels": sum(r["common_pixels"] == 0 for r in audited),
        "max_abs_delta_vs_aggregated_mg_ha": max(abs(r["delta_vs_aggregated"])
                                                  for r in audited if r["delta_vs_aggregated"] is not None),
        "eligible_spatial_population": len(eligible),
        "top20_common_mask_overlap": len(main_top & common_top),
        "top20_common_mask": common_rank,
        "main_top20_with_mask_mismatch": sum(r["mask_mismatch_pixels"] > 0 for r in audited
                                               if (r["cell_row"], r["cell_col"]) in main_top),
        "limitation": "Common mask fixes changing valid locations, not CTrees model error or ForTy classification error.",
    }
    with (PROJECT / "outputs/common_pixel_audit.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(audited[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(audited)
    (PROJECT / "outputs/common_pixel_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in (
        "cells_audited", "cells_mask_mismatch", "cells_no_common_pixels",
        "top20_common_mask_overlap", "main_top20_with_mask_mismatch",
        "max_abs_delta_vs_aggregated_mg_ha")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
