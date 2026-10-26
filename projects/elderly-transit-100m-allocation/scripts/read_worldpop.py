"""Read the WorldPop 100 m COG window covering the 53 mainland municipalities.

Use system Python (GDAL available):
  python3 projects/elderly-transit-100m-allocation/scripts/read_worldpop.py

The output is a compressed NPZ with pixel centres and values, plus an audit JSON.
"""

import json
import os
import sys
from pathlib import Path

for key in ("GDAL_DRIVER_PATH", "GDAL_DATA", "PROJ_DATA"):
    os.environ.pop(key, None)

import numpy as np
from osgeo import gdal

ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.name
OUTPUT = PROJECT / "outputs"
URL = (
    "https://huggingface.co/datasets/yuiseki/worldpop-jp-2026-01/resolve/main/"
    "cog/GIS/Population/Global_2015_2030/R2025A/2020/JPN/v1/100m/constrained/"
    "jpn_pop_2020_CN_100m_R2025A_v1.tif"
)
NODATA = -99999.0


def main():
    accounting = json.loads((OUTPUT / "input-accounting.json").read_text())
    lon_min, lat_min, lon_max, lat_max = accounting["bbox_epsg4326_padded"]
    ds = gdal.Open(f"/vsicurl/{URL}")
    if ds is None:
        raise RuntimeError("could not open WorldPop COG")
    gt = ds.GetGeoTransform()
    x0, px, _, y0, _, py = gt
    if px <= 0 or py >= 0 or abs(gt[2]) > 1e-12 or abs(gt[4]) > 1e-12:
        raise ValueError(f"unexpected geotransform {gt}")
    xoff = int(np.floor((lon_min - x0) / px)) - 2
    xend = int(np.ceil((lon_max - x0) / px)) + 2
    yoff = int(np.floor((lat_max - y0) / py)) - 2
    yend = int(np.ceil((lat_min - y0) / py)) + 2
    width = xend - xoff
    height = yend - yoff
    band = ds.GetRasterBand(1)
    values = band.ReadAsArray(xoff, yoff, width, height).astype(np.float32)
    cols = np.arange(width, dtype=np.int64)
    rows = np.arange(height, dtype=np.int64)
    lon = x0 + (xoff + cols + 0.5) * px
    lat = y0 + (yoff + rows + 0.5) * py

    nodata = values == NODATA
    zero = values == 0
    negative = (values < 0) & ~nodata
    valid = ~nodata
    if negative.any():
        raise ValueError(f"{int(negative.sum())} negative non-NoData pixels")
    if not valid.any():
        raise ValueError("no valid pixels in window")

    np.savez_compressed(
        ARTIFACTS / "worldpop-window.npz",
        lon=lon.astype(np.float64),
        lat=lat.astype(np.float64),
        values=values,
    )
    audit = {
        "source": URL,
        "crs": ds.GetProjection(),
        "geotransform": list(gt),
        "window": {"xoff": xoff, "yoff": yoff, "width": width, "height": height},
        "pixel_size_deg": [px, -py],
        "pixel_count": int(values.size),
        "nodata_count": int(nodata.sum()),
        "zero_count": int(zero.sum()),
        "negative_non_nodata_count": int(negative.sum()),
        "positive_count": int(((values > 0) & valid).sum()),
        "valid_count": int(valid.sum()),
        "valid_sum": float(values[valid].sum()),
        "valid_min": float(values[valid].min()),
        "valid_max": float(values[valid].max()),
        "nodata_value": NODATA,
        "gdaldriver": gdal.VersionInfo(),
    }
    (OUTPUT / "worldpop-window.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
