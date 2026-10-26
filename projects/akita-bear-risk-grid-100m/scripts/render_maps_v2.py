"""The Akita risk maps, redrawn by the map-context principles of the analysis-visualize skill: the whole prefecture,
and 10 km windows with place names, each with background boundaries and names, the legend outside, a caption with
the versions, the number of cells checked, and the overlapping texts counted (written to the JSON).

Usage:
    ... python render_maps_v2.py ART_DIR SCORES.npz MODEL OUT_DIR
"""

import json
import sys

import numpy as np

import mapkit as mk

MODEL_LABEL = {"B_env": "環境のモデル (2023〜2025 年度で学習)"}
SOURCE = "通報 akita-kumadas c7047ab (2026-09-30)。特徴量 ESA WorldCover 2021、国土地理院 DEM z12、WorldPop 2020、OSM 2026-08-31"


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.lines import Line2D

    art, scores_path, model, out = sys.argv[1:5]
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    meta = json.load(open(f"{art}/grid.json"))
    cells = pd.read_parquet(f"{art}/cells.parquet")
    score = np.load(scores_path)[model].astype(float)
    cls = mk.rank_classes(score)
    if len(cls) != len(cells) or len(cls) != meta.get("cells_in_prefecture", len(cls)):
        raise SystemExit(f"{len(cls)} scores for {len(cells)} cells")
    arr = np.full((meta["ny"], meta["nx"]), -1, dtype=np.int16)
    arr[cells.iy, cells.ix] = cls
    counts = [int((cls == k).sum()) for k in range(len(mk.CLASSES))]
    drawn = int((arr >= 0).sum())
    rep = np.load(f"{art}/reports_by_year.npz")["c2026"]
    ry, rx = np.nonzero((rep > 0) & (arr >= 0))
    pts_x = meta["x0"] + (rx + 0.5) * meta["size"]
    pts_y = meta["y0"] + (ry + 0.5) * meta["size"]
    full = (meta["x0"], meta["x0"] + meta["nx"] * meta["size"], meta["y0"], meta["y0"] + meta["ny"] * meta["size"])
    areas, pref = mk.background(full, "EPSG:6678", "05")
    caption = (f"{SOURCE}。100 m の正方形のセル (EPSG:6678)、県内 {drawn:,} セルを予測の順位で 6 段階に分けた。"
               f"{mk.ADMIN_SOURCE}。{mk.CRS_NOTE}。")
    record = {"cells_drawn": drawn, "cells_expected": len(cells), "cells_per_class": dict(zip([c for c, _ in mk.CLASSES], counts))}

    # the whole prefecture
    fig, ax = plt.subplots(figsize=(10, 12))
    mk.cm.draw_areas_under(ax, areas)
    mk.draw_cells(ax, arr, meta)
    mk.cm.draw_areas_over(ax, areas)
    texts = mk.cm.label_areas(ax, pref, full, min_share=0.002, fontsize=8)
    mk.finish(ax, full)
    leg = ax.legend(handles=mk.legend_handles(counts), title="2026 年度の通報のリスク (県内の順位)", loc="upper left",
                    bbox_to_anchor=(1.01, 1), fontsize=9, title_fontsize=9)
    ax.set_title(f"秋田県のどこで、2026 年度にクマの出没が通報されやすいか ({MODEL_LABEL.get(model, model)})", loc="left", fontsize=12)
    fig.text(0.02, 0.01, caption, fontsize=7, color="#444444", wrap=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    ov = mk.cm.text_overlaps(fig, texts, [leg])
    fig.savefig(f"{out}/risk-map-akita.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    record["akita"] = {"area_names": len(texts), "text_overlaps": ov}
    print("whole map: names", len(texts), "overlaps", ov)

    # 10 km windows centred on the reports of the three blocks with the most 2026 report cells, one per municipality
    blk = pd.DataFrame({"bx": rx // 100, "by": ry // 100, "unit": cells.set_index(["iy", "ix"]).reindex(list(zip(ry, rx))).code5.to_numpy()})
    top = blk.groupby(["bx", "by"]).agg(n=("unit", "size"), unit=("unit", lambda s: s.mode().iat[0])).reset_index()
    top = top.sort_values("n", ascending=False).drop_duplicates("unit").head(3)
    names = dict(zip(meta["codes"], meta["names"]))
    record["zooms"] = []
    for k, (_, r) in enumerate(top.iterrows()):
        inb = (rx // 100 == r.bx) & (ry // 100 == r.by)
        cx, cy = float(np.mean(pts_x[inb])), float(np.mean(pts_y[inb]))
        view = (cx - 5000, cx + 5000, cy - 5000, cy + 5000)
        fig, ax = plt.subplots(figsize=(8.5, 7))
        mk.cm.draw_areas_under(ax, areas)
        mk.draw_cells(ax, arr, meta)
        mk.cm.draw_areas_over(ax, areas)
        inside = (pts_x >= view[0]) & (pts_x < view[1]) & (pts_y >= view[2]) & (pts_y < view[3])
        ax.scatter(pts_x[inside], pts_y[inside], s=9, c="#123a6e", edgecolors="white", linewidths=0.4, zorder=5)
        places = mk.place_names(view, "EPSG:6678")
        ptexts = []
        rank = {"city": 0, "town": 1, "village": 2, "suburb": 3, "quarter": 4}
        from matplotlib import patheffects

        halo = [patheffects.withStroke(linewidth=2.2, foreground="white")]
        marker_of = {}
        for name, kind, px, py in places:
            big = kind in ("city", "town")
            t = ax.text(px, py, " " + name, fontsize=9 if big else 7, ha="left", va="center", color="#111111",
                        path_effects=halo, zorder=7)
            # a small open diamond, apart from the filled navy dots of the reports
            marker_of[t] = ax.plot(px, py, marker="D", ms=3.2 if big else 2.4, mfc="white", mec="#222222", mew=0.8,
                                   ls="", zorder=6)[0]
            ptexts.append((rank.get(kind, 5), t))
        mtexts = mk.cm.label_areas(ax, pref, view, min_share=0.05, fontsize=10)
        mk.finish(ax, view)
        extra = [Line2D([], [], marker="o", ls="", color="#123a6e", markeredgecolor="white", ms=6,
                        label=f"2026 年 4〜9 月に通報のあったセル ({int(inside.sum())})"),
                 Line2D([], [], marker="D", ls="", mfc="white", mec="#222222", ms=5, label="地名 (OSM)")]
        leg = ax.legend(handles=mk.legend_handles(counts, extra), title="リスク (県内の順位、セルの数は県全体)",
                        loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, title_fontsize=8)
        muni = names[r.unit]
        ax.set_title(f"{muni}付近の 10 km 四方: どの 100 m のセルで通報されやすいか", loc="left", fontsize=11)
        fig.text(0.02, 0.01, caption + f" {mk.OSM_SOURCE} の place (市、町、村、地区)。重なる地名は、市、町、村、地区の順に残して間引いた。", fontsize=6.5,
                 color="#444444", wrap=True)
        fig.tight_layout(rect=(0, 0.06, 1, 1))
        # municipality names first, then places by kind; a name that would overlap a kept one is not drawn
        kept, hidden = mk.thin_labels(fig, [(-1, t) for t in mtexts] + ptexts, [leg])
        for t, m in marker_of.items():
            m.set_visible(t.get_visible())  # no marker without its name
        ov = mk.cm.text_overlaps(fig, kept, [leg])
        path = f"{out}/risk-map-zoom-{k + 1}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        record["zooms"].append({"municipality": muni, "window_epsg6678": list(view), "report_cells": int(inside.sum()),
                                "place_names": len(places), "names_drawn": len(kept), "names_hidden_to_avoid_overlap": hidden,
                                "text_overlaps": ov, "png": path})
        print(muni, "places", len(places), "drawn", len(kept), "hidden", hidden, "overlaps", len(ov))
    json.dump(record, open(f"{out}/risk-maps-v2.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
