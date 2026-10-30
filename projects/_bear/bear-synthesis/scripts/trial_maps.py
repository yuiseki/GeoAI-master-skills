"""Two maps for the synthesis that the projects did not draw: (1) where the fixed B2 map caught and missed the
April-September report cells of 2025 and 2026, the gap that led to the Akita City and activation work (R041-R043),
and (2) what the within-season activation (R043/R044 setting, r 2 km, alpha 1) changed in the top 5% in the 2024
week with the most Akita City positives. Nothing is refitted; counts are checked against the saved outputs.

From repository root:
    env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy --with pandas --with pyarrow --with shapely \
      --with matplotlib --with pyproj python projects/_bear/bear-synthesis/scripts/trial_maps.py \
      artifacts/_bear/akita-bear-risk-grid-100m projects/_bear/bear-synthesis/outputs
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
GRID_SCRIPTS = HERE.parents[1] / "akita-bear-risk-grid-100m" / "scripts"
sys.path.insert(0, str(GRID_SCRIPTS))

K = 0.05
B2 = "eval/b2_confirm_2023-2024_to_2025_scores.npz"
B1 = "eval/b1_dev_2023_to_2024_scores.npz"
R041 = HERE.parents[1] / "akita-bear-risk-grid-100m" / "outputs" / "b2_fixed_score_municipal_decomposition.json"
SOURCE = ("通報 akita-kumadas c7047ab (2026-09-30)、4〜9 月。100 m のセル (EPSG:6678)。"
          "市町村界 jp-admin-2026-09 (e6c87b1)")
C_TOP, C_HIT, C_MISS = "#ef9a5c", "#123a6e", "#d1176b"
C_KEPT, C_ADD, C_DROP = "#f7c9a3", "#d95f02", "#5e57b0"


def top_set(score, k):
    """The first ceil(k * n) cells of metrics.rank_order(seed=0), as a mask (R041's integer top set)."""
    import metrics as mt

    n = len(score)
    mask = np.zeros(n, bool)
    mask[mt.rank_order(np.asarray(score, dtype=float), seed=0)[:math.ceil(k * n - 1e-9)]] = True
    return mask


def hit_miss(pos, top):
    return pos & top, pos & ~top


def selection_change(e_top, m_top):
    """(in both, only in M, only in E)."""
    return e_top & m_top, m_top & ~e_top, e_top & ~m_top


def busiest_week(counts):
    return int(np.argmax(counts))


def block_net(inside, added, dropped, b):
    """Cells added minus cells dropped, summed over b x b blocks of the grid (the edge padded with zeros)."""
    arr = np.zeros(inside.shape, dtype=np.int32)
    arr[inside] = added.astype(np.int32) - dropped.astype(np.int32)
    ny, nx = -(-arr.shape[0] // b) * b, -(-arr.shape[1] // b) * b
    pad = np.zeros((ny, nx), dtype=np.int32)
    pad[:arr.shape[0], :arr.shape[1]] = arr
    return pad.reshape(ny // b, b, nx // b, b).sum(axis=(1, 3))


def load(art):
    import duckdb
    import pandas as pd
    import pyproj

    from grid import Grid
    import labels as lb

    meta = json.loads((art / "grid.json").read_text(encoding="utf-8"))
    grid = Grid(meta["x0"], meta["y0"], meta["nx"], meta["ny"], meta["size"])
    with np.load(art / "grid_mask.npz") as m:
        muni = m["muni"]
    inside = muni >= 0
    cells = pd.read_parquet(art / "cells.parquet", columns=["ix", "iy"])
    iy0, ix0 = np.nonzero(inside)
    if not (np.array_equal(cells.ix.to_numpy(), ix0) and np.array_equal(cells.iy.to_numpy(), iy0)):
        raise ValueError("cells.parquet order differs from the prefecture mask")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    raw = con.execute("""SELECT longitude, latitude, observed_at FROM read_parquet(?)
                         WHERE species = ? AND observed_at >= ? AND observed_at < ?""",
                      [lb.SIGHTING, "ツキノワグマ", "2024-04-01", "2026-10-01"]).fetchnumpy()
    tr = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:6678", always_xy=True)
    x, y = tr.transform(raw["longitude"], raw["latitude"])
    dates = np.asarray(raw["observed_at"], dtype="datetime64[m]")
    xc = meta["x0"] + (ix0 + 0.5) * meta["size"]
    yc = meta["y0"] + (iy0 + 0.5) * meta["size"]
    city = muni[inside] == meta["codes"].index("05201")
    return meta, grid, muni, inside, x, y, dates, xc, yc, city


def season_positive(grid, muni, inside, x, y, dates, year):
    import seasonal_activation as sa

    iy, ix, _ = sa.season_reports(grid, muni, x, y, dates, year)
    return sa.grid_counts(iy, ix, np.ones(len(iy), bool), muni.shape)[inside] > 0


def base(ax, areas, view):
    import mapkit as mk

    mk.cm.draw_areas_under(ax, areas)
    mk.cm.draw_areas_over(ax, areas)
    mk.finish(ax, view)


def draw_classes(ax, meta, inside, classes, colours, interpolation):
    """Cells as their 100 m squares: classes 1..len(colours) per prefecture cell, 0 left empty."""
    from matplotlib.colors import ListedColormap

    arr = np.zeros(inside.shape, dtype=np.int16)
    arr[inside] = classes
    extent = [meta["x0"], meta["x0"] + meta["nx"] * meta["size"], meta["y0"], meta["y0"] + meta["ny"] * meta["size"]]
    ax.imshow(np.ma.masked_equal(arr, 0), origin="lower", extent=extent, cmap=ListedColormap(colours), vmin=0.5,
              vmax=len(colours) + 0.5, interpolation=interpolation, zorder=2)


def outline(ax, pref, name, **kw):
    import shapely

    for n, g in pref:
        if n == name:
            for p in getattr(g, "geoms", [g]):
                xs, ys = shapely.get_coordinates(p.exterior).T
                ax.plot(xs, ys, zorder=8, **kw)


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    import mapkit as mk
    import seasonal_activation as sa

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("art", type=Path)
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
    meta, grid, muni, inside, x, y, dates, xc, yc, city = load(a.art)
    full = (meta["x0"], meta["x0"] + meta["nx"] * meta["size"], meta["y0"], meta["y0"] + meta["ny"] * meta["size"])
    areas, pref = mk.background(full, "EPSG:6678", "05")
    record = {"source": SOURCE}

    # (1) the fixed B2 map against 2025 and 2026
    with np.load(a.art / B2) as s:
        top = top_set(s["B_env"], K)
    r041 = json.loads(R041.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 2, figsize=(13, 8.6))
    record["gaps"] = {}
    for ax, year in zip(axes, (2025, 2026)):
        pos = season_positive(grid, muni, inside, x, y, dates, year)
        hit, miss = hit_miss(pos, top)
        ref = r041["years"][str(year)]
        rc = r041["akita_city"][str(year)]
        got = {"n_positive": int(pos.sum()), "n_captured": int(hit.sum()),
               "city_positive": int((pos & city).sum()), "city_captured": int((hit & city).sum())}
        if (got["n_positive"], got["n_captured"], got["city_positive"], got["city_captured"]) != \
                (ref["n_positive"], ref["n_captured"], rc["n_positive"], rc["n_captured"]):
            raise ValueError(f"{year} counts differ from R041: {got}")
        got["capture"] = got["n_captured"] / got["n_positive"]
        got["city_recall"] = got["city_captured"] / got["city_positive"]
        got["city_share"] = got["city_positive"] / got["n_positive"]
        record["gaps"][str(year)] = got
        mk.cm.draw_areas_under(ax, areas)
        draw_classes(ax, meta, inside, top.astype(np.int16), [C_TOP], "antialiased")
        mk.cm.draw_areas_over(ax, areas)
        ax.scatter(xc[hit], yc[hit], s=2.2, c=C_HIT, lw=0, zorder=4, rasterized=True)
        ax.scatter(xc[miss], yc[miss], s=2.2, c=C_MISS, lw=0, zorder=5, rasterized=True)
        outline(ax, pref, "秋田市", color="#111111", lw=1.4)
        mk.finish(ax, full)
        ax.set_title(f"{year} 年 4〜9 月: 当たり {got['capture']:.3f}\n秋田市は陽性の {got['city_share']:.1%}、"
                     f"そのうち当たり {got['city_recall']:.1%}", loc="left", fontsize=10)
    handles = [Line2D([], [], marker="s", ls="", color=C_TOP, ms=7, label="B2 の上位 5% (2023+2024 年度で学習、両年で同じ)"),
               Line2D([], [], marker="o", ls="", color=C_HIT, ms=5, label="通報のあったセル、上位 5% の中"),
               Line2D([], [], marker="o", ls="", color=C_MISS, ms=5, label="通報のあったセル、上位 5% の外 (取り逃し)"),
               Line2D([], [], color="#111111", lw=1.4, label="秋田市の境")]
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.035))
    fig.suptitle("同じ地図で 2 つの年を採点すると、2026 年は秋田市に陽性が寄り、そこで取り逃しが増えた",
                 x=0.02, ha="left", fontsize=12)
    fig.text(0.02, 0.008, SOURCE + "。上位 5% は rank_order(seed=0) の先頭 58,411 セル (R041 と同じ整数の集合)。",
             fontsize=7, color="#444444")
    fig.tight_layout(rect=(0, 0.08, 1, 0.97))
    fig.savefig(a.out / "map-gaps-2025-2026.png", dpi=150)
    plt.close(fig)

    # (2) what activation changed in one 2024 week
    with np.load(a.art / B1) as s:
        env = s["B_env"].astype(float)
    kern = sa.disk_kernel(2000, grid.size)
    iy, ix, day = sa.season_reports(grid, muni, x, y, dates, 2024)
    origins = sa.week_origins(2024)
    weekly = []
    for t in origins:
        win, target, _ = sa.week_data(iy, ix, day, t, muni.shape, inside, np.datetime64("2024-04-01"))
        weekly.append((win, target))
    w = busiest_week([int((tg & city).sum()) for _, tg in weekly])
    shares = []
    for win, target in weekly:
        m_top = top_set(sa.mixed(env, sa.activity(win, kern)[inside], 1), K)
        shares.append(float((m_top & city).sum() / m_top.sum()))
    win, target = weekly[w]
    e_top = top_set(env, K)
    m_top = top_set(sa.mixed(env, sa.activity(win, kern)[inside], 1), K)
    kept, added, dropped = selection_change(e_top, m_top)
    cpos = target & city
    act = {"week": str(origins[w]), "city_positives": int(cpos.sum()), "positives": int(target.sum()),
           "window_reports": int(win[inside].sum()),
           "city_share_of_top_E": float((e_top & city).sum() / e_top.sum()),
           "city_share_of_top_M": float((m_top & city).sum() / m_top.sum()),
           "city_share_of_top_M_mean_21_weeks": float(np.mean(shares)),
           "added": int(added.sum()), "added_in_city": int((added & city).sum()),
           "city_positives_caught_E": int((cpos & e_top).sum()), "city_positives_caught_M": int((cpos & m_top).sum())}
    record["activation_2024"] = act
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 8.2), gridspec_kw={"width_ratios": [1, 1.25]})
    zoom_cells = city
    zx0, zx1 = xc[zoom_cells].min() - 1500, xc[zoom_cells].max() + 1500
    zy0, zy1 = yc[zoom_cells].min() - 1500, yc[zoom_cells].max() + 1500
    zoom = (zx0, zx1, zy0, zy1)
    net = block_net(inside, added, dropped, 20)
    lim = float(np.abs(net).max())
    act["block_net_max_cells"] = int(lim)
    mk.cm.draw_areas_under(a1, areas)
    ext = [meta["x0"], meta["x0"] + net.shape[1] * 20 * meta["size"],
           meta["y0"], meta["y0"] + net.shape[0] * 20 * meta["size"]]
    im = a1.imshow(np.ma.masked_equal(net, 0), origin="lower", extent=ext, cmap="PuOr_r", vmin=-lim, vmax=lim,
                   interpolation="nearest", zorder=2)
    mk.cm.draw_areas_over(a1, areas)
    a1.scatter(xc[target], yc[target], s=3, facecolors="none", edgecolors="#111111", lw=0.5, zorder=6)
    outline(a1, pref, "秋田市", color="#111111", lw=1.4)
    mk.finish(a1, full)
    cb = fig.colorbar(im, ax=a1, fraction=0.035, pad=0.02)
    cb.set_label("2 km 四方ごとの、M で入ったセル − 外れたセル", fontsize=8)
    mk.cm.draw_areas_under(a2, areas)
    draw_classes(a2, meta, inside, (kept * 1 + dropped * 2 + added * 3).astype(np.int16), [C_KEPT, C_DROP, C_ADD],
                 "nearest")
    mk.cm.draw_areas_over(a2, areas)
    a2.scatter(xc[target], yc[target], s=14, facecolors="none", edgecolors="#111111", lw=0.7, zorder=6)
    outline(a2, pref, "秋田市", color="#111111", lw=1.4)
    mk.finish(a2, zoom)
    a1.set_title(f"県全体: 上位 5% のうち秋田市のセルは\nE {act['city_share_of_top_E']:.1%} → M {act['city_share_of_top_M']:.1%}",
                 loc="left", fontsize=10)
    a2.set_title(f"秋田市: この週の陽性 {act['city_positives']} セルのうち上位 5% に入ったのは\n"
                 f"E {act['city_positives_caught_E']} → M {act['city_positives_caught_M']}", loc="left", fontsize=10)
    handles = [Line2D([], [], marker="s", ls="", color=C_KEPT, ms=7, label="E でも M でも上位 5%"),
               Line2D([], [], marker="s", ls="", color=C_ADD, ms=7, label="M で上位 5% に入った (直前 28 日に近くで通報)"),
               Line2D([], [], marker="s", ls="", color=C_DROP, ms=7, label="M で上位 5% から外れた"),
               Line2D([], [], marker="o", ls="", mfc="none", mec="#111111", ms=6, label="翌週に通報のあったセル"),
               Line2D([], [], color="#111111", lw=1.4, label="秋田市の境")]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.035))
    fig.suptitle(f"活性化は県の上位 5% を通報の続く場所へ動かす ({act['week']} からの 1 週、2024 年)",
                 x=0.02, ha="left", fontsize=12)
    fig.text(0.02, 0.008, SOURCE + "。E は B1 の B_env (2023 年度で学習)、M = E × (直前 28 日の 2 km 以内の通報 + 1)。"
             "週は 2024 年の 21 週のうち秋田市の陽性が最も多い週。", fontsize=7, color="#444444")
    fig.tight_layout(rect=(0, 0.08, 1, 0.97))
    fig.savefig(a.out / "map-activation-2024.png", dpi=150)
    plt.close(fig)

    (a.out / "trial_maps.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
