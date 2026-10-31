"""The GSI depth of the four versions on the analysis grid, read from the map tiles through the PDF legend.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with scipy --with pyproj --with pillow python scripts/08_gsi_depth.py [--max-dist 10]

Writes artifacts/.../gsi_depth[_d<max-dist>].npz (depth_0922 ... depth_1001, nan where no depth), outputs/legend_<v>.csv
and outputs/gsi_depth[_d<max-dist>].json (per version: tile pixels, pixels far from the legend, cells with depth,
the depth quantiles, and the painted area against the outline's).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
fb = __import__("07_fetch_b")
from sarb import colour_to_depth, legend_table, tile_pixel_lonlat, to_grid_mean  # noqa: E402

OUT = HERE.parent / "outputs"


def mosaic(v):
    d = fb.RAW_B / "tiles" / v
    names = [p.stem for p in d.iterdir() if p.suffix in (".png", ".404")]
    xy = np.array([[int(s) for s in n.split("_")] for n in names])
    x0, y0 = xy.min(0)
    x1, y1 = xy.max(0)
    m = np.zeros(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256, 4), np.uint8)
    for p in d.glob("*.png"):
        x, y = (int(s) for s in p.stem.split("_"))
        m[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = np.array(Image.open(p).convert("RGBA"))
    return m, x0, y0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-dist", type=float, default=10.0)
    args = ap.parse_args()
    suffix = "" if args.max_dist == 10.0 else f"_d{args.max_dist:g}"
    g = np.load(fb.ART / "grid.npz")
    shape = g["vv_a"].shape
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32654", always_xy=True)
    out, summary, legends = {}, {}, {}
    for v in fb.VERSIONS:
        leg = np.load(fb.RAW_B / "pdf" / f"legend_{v}.npz")
        depths, colours = legend_table(leg["rgb"], leg["alpha"])
        legends[v] = colours
        np.savetxt(OUT / f"legend_{v}.csv", np.column_stack([depths, colours]), delimiter=",", fmt="%.4f",
                   header="depth_m,r,g,b", comments="")
        m, x0, y0 = mosaic(v)
        depth, n_far = colour_to_depth(m, depths, colours, args.max_dist)
        lon, lat = tile_pixel_lonlat(x0, y0, 16, m.shape[:2])
        x, y = to_utm.transform(lon.ravel(), lat.ravel())
        # a transparent pixel counts as no depth in the cover rule; only pixels inside the tiles fetched count
        grid = to_grid_mean(depth.ravel(), np.asarray(x), np.asarray(y), g["transform"], shape)
        out[f"depth_{v}"] = grid.astype(np.float32)
        ref = g[f"ref_{v}"]
        has = ~np.isnan(grid)
        summary[v] = {"tile_pixels_opaque": int((m[..., 3] > 0).sum()), "far_from_legend": n_far,
                      "cells_with_depth": int(has.sum()), "depth_km2": round(has.sum() * 100 / 1e6, 4),
                      "outline_km2": round(ref.sum() * 100 / 1e6, 4),
                      "outline_cells_with_depth_share": round(float((has & ref).sum() / ref.sum()), 4),
                      "depth_cells_inside_outline_share": round(float((has & ref).sum() / has.sum()), 4),
                      "depth_m_quantiles": [round(float(q), 3) for q in np.nanquantile(grid, [0, 0.1, 0.5, 0.9, 1])]}
    same = all(np.array_equal(legends["0922"], legends[v]) for v in fb.VERSIONS)
    summary["legend_same_in_all_versions"] = bool(same)
    summary["max_dist"] = args.max_dist
    np.savez_compressed(fb.ART / f"gsi_depth{suffix}.npz", **out)
    (OUT / f"gsi_depth{suffix}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
