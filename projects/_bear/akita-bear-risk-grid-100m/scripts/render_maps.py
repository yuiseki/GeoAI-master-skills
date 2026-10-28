"""Maps of the 100 m risk grid: PNG maps for the report and a Web Mercator image for the interactive map.

The risk of a cell is its rank among the prefecture's cells (percentile of the model score), in classes:
top 1%, 1-5%, 5-10%, 10-25%, 25-50%, the rest. A rank, not a probability: the probability of a report in a
cell changes with the year's level (see the report).

Usage:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy \
        --with pandas --with pyarrow --with matplotlib --with shapely --with pyproj --with pillow \
        python render_maps.py ART_DIR SCORES.npz MODEL OUT_DIR WEB_DIR
"""

import json
import sys

import numpy as np

from grid import CRS, Grid

# (label, upper bound of the share from the top)
CLASSES = [("下位 50%", 1.0), ("上位 25〜50%", 0.50), ("上位 10〜25%", 0.25), ("上位 5〜10%", 0.10), ("上位 1〜5%", 0.05), ("上位 1%", 0.01)]
COLOURS = ["#f2f0f7", "#fde0c5", "#facba6", "#f59e72", "#e5543b", "#9b0a19"]
MODEL_LABEL = {"B_env": "環境のモデル", "M_full": "環境と過去の通報のモデル"}
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"


def risk_classes(score):
    """Class 0 (the bottom half) .. 5 (top 1%) by the rank of the score (ties: the order of the cells)."""
    n = len(score)
    order = np.argsort(-score, kind="stable")
    top_share = np.empty(n)
    top_share[order] = (np.arange(n) + 1) / n
    cls = np.zeros(n, dtype=np.int16)
    for k, (_, bound) in enumerate(CLASSES):
        if k == 0:
            continue
        cls[top_share <= bound] = k
    return cls


def rank_bytes(score, ix, iy, nx, ny):
    """[ny, nx] uint8: ceil(top share x 200), so 1 is the top 0.5% and 200 the bottom; 0 outside the prefecture."""
    n = len(score)
    order = np.argsort(-score, kind="stable")
    top_share = np.empty(n)
    top_share[order] = (np.arange(n) + 1) / n
    b = np.zeros((ny, nx), dtype=np.uint8)
    b[iy, ix] = np.clip(np.ceil(top_share * 200), 1, 200).astype(np.uint8)
    return b


def to_array(values, ix, iy, nx, ny, fill=-1):
    arr = np.full((ny, nx), fill, dtype=np.asarray(values).dtype)
    arr[iy, ix] = values
    return arr


def sample_to_pixels(arr, grid, xs, ys, to_grid):
    """Class of the cell under each pixel centre of an image (xs west to east, ys north to south)."""
    X, Y = np.meshgrid(xs, ys)
    gx, gy = to_grid(X.ravel(), Y.ravel())
    ix, iy, ok = grid.index(np.asarray(gx), np.asarray(gy))
    out = np.full(X.size, -1, dtype=arr.dtype)
    out[ok] = arr[iy[ok], ix[ok]]
    return out.reshape(X.shape)


def mercator_frame(g, zoom=12):
    """Pixel centres (xs west to east, ys north to south) of a Web Mercator image covering the grid, at the
    pixel size of a zoom level, snapped to that zoom's pixel edges; also its bounds and pixel size."""
    import pyproj

    to3857 = pyproj.Transformer.from_crs(CRS, "EPSG:3857", always_xy=True)
    cx = [g.x0, g.x0 + g.nx * g.size]
    cy = [g.y0, g.y0 + g.ny * g.size]
    X, Y = to3857.transform([cx[0], cx[0], cx[1], cx[1]], [cy[0], cy[1], cy[0], cy[1]])
    res = 2 * 20037508.342789244 / (256 * 2 ** zoom)
    x0, x1 = np.floor(min(X) / res) * res, np.ceil(max(X) / res) * res
    y0, y1 = np.floor(min(Y) / res) * res, np.ceil(max(Y) / res) * res
    xs = x0 + (np.arange(int(round((x1 - x0) / res))) + 0.5) * res
    ys = y1 - (np.arange(int(round((y1 - y0) / res))) + 0.5) * res
    return xs, ys, (x0, y0, x1, y1), res


def municipal_lines():
    import duckdb
    import pyproj
    import shapely

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    rows = con.execute(f"SELECT name, ST_AsWKB(geometry) FROM read_parquet('{ADMIN}') WHERE pref_code = '05' AND ward IS NULL AND geometry IS NOT NULL").fetchall()
    tr = pyproj.Transformer.from_crs("EPSG:4612", CRS, always_xy=True)

    def f(c):
        return np.column_stack(tr.transform(c[:, 0], c[:, 1]))

    return [(n, shapely.transform(shapely.from_wkb(bytes(w)), f)) for n, w in rows]


def draw(ax, cls_arr, g, window=None, munis=None, points=None, label_munis=False):
    from matplotlib.colors import ListedColormap

    cmap = ListedColormap(COLOURS)
    cmap.set_under("white")
    extent = [g.x0, g.x0 + g.nx * g.size, g.y0, g.y0 + g.ny * g.size]
    ax.imshow(np.ma.masked_less(cls_arr, 0), origin="lower", extent=extent, cmap=cmap, vmin=-0.5, vmax=len(CLASSES) - 0.5, interpolation="nearest")
    if munis:
        import shapely

        for name, geom in munis:
            for part in getattr(geom, "geoms", [geom]):
                x, y = part.exterior.xy
                ax.plot(x, y, color="#555555", lw=0.4)
            if label_munis:
                p = geom.representative_point()
                ax.text(p.x, p.y, name, fontsize=6, ha="center", va="center", color="#222222")
    if points is not None and len(points[0]):
        ax.scatter(points[0], points[1], s=4, c="#1f3b73", marker="o", linewidths=0, label="2026 年度 4〜9 月の通報")
    if window:
        ax.set_xlim(window[0], window[2])
        ax.set_ylim(window[1], window[3])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    import pyproj
    from matplotlib.patches import Patch
    from PIL import Image

    art, scores_path, model, out, web = sys.argv[1:6]
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    meta = json.load(open(f"{art}/grid.json"))
    g = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    cells = pd.read_parquet(f"{art}/cells.parquet")
    score = np.load(scores_path)[model].astype(float)
    if len(score) != len(cells):
        raise SystemExit(f"{len(score)} scores for {len(cells)} cells")
    cls = risk_classes(score)
    arr = to_array(cls, cells.ix.to_numpy(), cells.iy.to_numpy(), g.nx, g.ny)
    rep = np.load(f"{art}/reports_by_year.npz")["c2026"]
    py, px = np.nonzero(rep > 0)
    pts = (g.x0 + (px + 0.5) * g.size, g.y0 + (py + 0.5) * g.size)
    munis = municipal_lines()
    legend = [Patch(color=c, label=l) for (l, _), c in zip(CLASSES[::-1], COLOURS[::-1])]

    fig, ax = plt.subplots(figsize=(8, 12))
    draw(ax, arr, g, munis=munis, label_munis=True)
    ax.set_title(f"秋田県 100 m セルのクマ出没通報リスク (2026 年度、{MODEL_LABEL.get(model, model)})\n県内 {len(cells):,} セルの中の順位", fontsize=11)
    ax.legend(handles=legend, loc="lower left", fontsize=8, frameon=True)
    fig.tight_layout()
    fig.savefig(f"{out}/risk-map-akita.png", dpi=170)
    plt.close(fig)

    # zooms: the 10 km windows (on the 10 km blocks) with the most 2026 reports, one per municipality
    blk = pd.DataFrame({"bx": px // 100, "by": py // 100, "code5": cells.set_index(["iy", "ix"]).reindex(list(zip(py, px))).code5.to_numpy()})
    top = blk.groupby(["bx", "by"]).agg(n=("code5", "size"), code5=("code5", lambda s: s.mode().iat[0])).reset_index()
    top = top.sort_values("n", ascending=False).drop_duplicates("code5").head(3)
    names = dict(zip(meta["codes"], meta["names"]))
    zooms = []
    fig = plt.figure(figsize=(15, 6.3))
    gs = fig.add_gridspec(2, 3, height_ratios=[12, 1])
    axes = [fig.add_subplot(gs[0, k]) for k in range(3)]
    sel_x, sel_y = pts
    for ax, (_, r) in zip(axes, top.iterrows()):
        # centre the 10 km window on the reports of that block, so it shows land rather than a block corner
        inb = (px // 100 == r.bx) & (py // 100 == r.by)
        cx, cy = float(np.mean(sel_x[inb])), float(np.mean(sel_y[inb]))
        win = (cx - 50 * g.size, cy - 50 * g.size, cx + 50 * g.size, cy + 50 * g.size)
        n_in = int(((sel_x >= win[0]) & (sel_x < win[2]) & (sel_y >= win[1]) & (sel_y < win[3])).sum())
        draw(ax, arr, g, window=win, munis=munis, points=pts)
        ax.set_title(f"{names[r.code5]} 付近 (10 km 四方、2026 年度 4〜9 月に通報のあったセル {n_in})", fontsize=10)
        zooms.append({"municipality": names[r.code5], "window_epsg6678": [float(v) for v in win], "cells_with_2026_reports": n_in})
    lax = fig.add_subplot(gs[1, :])
    lax.axis("off")
    lax.legend(handles=legend + [plt.Line2D([], [], marker="o", ls="", color="#1f3b73", ms=4, label="2026 年度 4〜9 月に通報のあったセル")],
               loc="center", ncol=7, fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(f"{out}/risk-map-zooms.png", dpi=150)
    plt.close(fig)

    # the Web Mercator image for the interactive map: pixels of zoom 12 (38.2 m in EPSG:3857, about 29 m on the
    # ground here; a 100 m cell is about 3.4 pixels). Zoom 13 would be about 100 million pixels.
    back = pyproj.Transformer.from_crs("EPSG:3857", CRS, always_xy=True)
    xs, ys, (x0, y0, x1, y1), res = mercator_frame(g)
    img = np.vstack([sample_to_pixels(arr, g, xs, ys[i:i + 512], back.transform) for i in range(0, len(ys), 512)])
    rgba = np.zeros(img.shape + (4,), dtype=np.uint8)
    for k, c in enumerate(COLOURS):
        if k == 0:
            continue  # the bottom half is left clear, so the base map shows
        rgb = tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
        rgba[img == k] = rgb + (210,)
    Image.fromarray(rgba, "RGBA").save(f"{web}/risk.png", optimize=True)
    lonlat = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    (w_, n_), (e_, s_) = lonlat.transform(x0, y1), lonlat.transform(x1, y0)
    info = {"image": "risk.png", "pixels": [int(img.shape[1]), int(img.shape[0])], "pixel_m_epsg3857": res,
            "coordinates": [[w_, n_], [e_, n_], [e_, s_], [w_, s_]], "classes": [l for l, _ in CLASSES],
            "colours": COLOURS, "model": model, "zooms": zooms,
            "cells_per_class": {CLASSES[k][0]: int((cls == k).sum()) for k in range(len(CLASSES))}}
    # the rank of every cell, row 0 = the south edge, for looking up the cell under the pointer
    rank_bytes(score, cells.ix.to_numpy(), cells.iy.to_numpy(), g.nx, g.ny).tofile(f"{web}/rank.bin")
    info["grid"] = {**g.to_dict(), "rank_file": "rank.bin", "rank_encoding": "uint8, row 0 south, ceil(top share x 200), 0 outside"}
    json.dump(info, open(f"{web}/risk.json", "w"), ensure_ascii=False, indent=1)
    json.dump(info, open(f"{out}/risk-map.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
