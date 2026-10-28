"""Side-by-side maps of one held-out region: the model fitted on the other three regions with the base features and
with the climate normals added, as rank classes, with the region's report cells on top.

Drawn by the map-context principles of the analysis-visualize skill (through mapkit.py of akita-bear-risk-grid-100m):
the cells as their squares, municipal boundaries and names from frozen data, one legend outside the maps with the
number of cells per class, a caption with the versions, the number of cells drawn checked against the region, and the
overlapping texts counted (written to the JSON). The scores are cached in the artifacts directory.

Usage:
    ... python map_compare.py TARGET OUT.png
"""

import json
import os
import sys

import numpy as np

import run_matrix as rm

sys.path.insert(0, os.path.join(rm.HERE, "../../akita-bear-risk-grid-100m/scripts"))
import mapkit as mk  # noqa: E402

PREF = {"gifu": ("21", "岐阜県"), "kyoto": ("26", "京都府"), "ishikawa": ("17", "石川県"), "akita": ("05", "秋田県")}
JA = {"akita": "秋田", "gifu": "岐阜", "kyoto": "京都", "ishikawa": "石川"}
REPORTS = {"gifu": "通報 gifu-bear-sighting b7f5947 (FY2014〜FY2025)", "kyoto": "通報 kyoto-bear-sighting a2a50c4 (FY2009〜2018-12)",
           "ishikawa": "通報 ishikawa-bear-incident d2b77a2 (2019-01〜2025-06)", "akita": "通報 akita-kumadas c7047ab (2022-04〜2026-09)"}
VARIANTS = [("base", "基準 (OSM の建物、道路、川)"), ("clim", "平年値を足した")]


def scores(target, train):
    path = f"{rm.SRC}/{target}/map_scores.npz"
    if os.path.exists(path):
        return dict(np.load(path))
    out = {}
    for v, _ in VARIANTS:
        X, _ = rm.design(target, v)
        out[v] = rm.fit(train, v).predict_proba(X)[:, 1]
    np.savez_compressed(path, **out)
    return out


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.lines import Line2D

    target, out = sys.argv[1], sys.argv[2]
    train = [r for r in rm.REGIONS if r != target]
    art = rm.ART[target]
    meta = json.load(open(f"{art}/grid.json"))
    crs = meta["crs"]
    cells = pd.read_parquet(f"{art}/cells.parquet", columns=["ix", "iy"])
    y, _ = rm.labels(target)
    s = scores(target, train)
    if any(len(s[v]) != len(cells) for v, _ in VARIANTS) or len(cells) != meta["cells_in_prefecture"]:
        raise SystemExit(f"scores {[len(s[v]) for v, _ in VARIANTS]} for {len(cells)} cells, {meta['cells_in_prefecture']} expected")
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    full = (meta["x0"], meta["x0"] + meta["nx"] * meta["size"], meta["y0"], meta["y0"] + meta["ny"] * meta["size"])
    areas, pref = mk.background(full, crs, PREF[target][0])
    px = meta["x0"] + (cells.ix.to_numpy()[y] + 0.5) * meta["size"]
    py = meta["y0"] + (cells.iy.to_numpy()[y] + 0.5) * meta["size"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 8))
    record = {"target": target, "train": train, "crs": crs, "cells_expected": int(meta["cells_in_prefecture"]),
              "report_cells": int(y.sum()), "panels": {}}
    texts, counts = [], None
    for ax, (v, title) in zip(axes, VARIANTS):
        cls = mk.rank_classes(s[v])
        arr = np.full((meta["ny"], meta["nx"]), -1, dtype=np.int16)
        arr[cells.iy, cells.ix] = cls
        counts = [int((cls == k).sum()) for k in range(len(mk.CLASSES))]
        cap = rm.sr.capture(rm.sr.rank_order(s[v], seed=0), y, 0.05)
        mk.cm.draw_areas_under(ax, areas)
        mk.draw_cells(ax, arr, meta)
        mk.cm.draw_areas_over(ax, areas)
        ax.scatter(px, py, s=0.5, c="#123a6e", linewidths=0, zorder=5)
        texts += mk.cm.label_areas(ax, pref, full, min_share=0.01, fontsize=7)
        mk.finish(ax, full, crs)
        ax.set_title(f"{title}\n通報のあったセルのうち上位 5% に入った割合 (capture@5%) {cap:.3f}", loc="left", fontsize=10)
        record["panels"][v] = {"capture5": cap, "cells_drawn": int((arr >= 0).sum())}
    extra = [Line2D([], [], marker="o", ls="", color="#123a6e", ms=4, label=f"通報のあったセル ({int(y.sum()):,})")]
    leg = axes[1].legend(handles=mk.legend_handles(counts, extra), title=f"リスク ({JA[target]}の中の順位)", loc="upper left",
                         bbox_to_anchor=(1.02, 1), fontsize=8, title_fontsize=8)
    fig.suptitle(f"{PREF[target][1]}を、学習に使っていない地域として当てる (学習は {'、'.join(JA[r] for r in train)})", x=0.01,
                 ha="left", fontsize=12)
    caption = (f"{REPORTS[target]}。特徴量 ESA WorldCover 2021、国土地理院 DEM z12、WorldPop 2020、OSM 2026-08-31、"
               f"右は国土数値情報 G02 平年値メッシュ (2022 年版) を足した。100 m の正方形のセル ({crs})、"
               f"{meta['cells_in_prefecture']:,} セルを予測の順位で 6 段階に分けた (両方の地図で同じ数)。"
               f"{mk.ADMIN_SOURCE}。背景の JGD2000 と格子の JGD2011 系の差は約 1 m で、図の線の幅より小さい。")
    fig.text(0.01, 0.01, caption, fontsize=7, color="#444444", wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    kept, hidden = mk.thin_labels(fig, [(0, t) for t in texts], [leg])
    record["area_names_drawn"], record["area_names_hidden"] = len(kept), hidden
    record["text_overlaps"] = mk.cm.text_overlaps(fig, kept, [leg])
    fig.savefig(out, dpi=140, bbox_inches="tight")
    json.dump(record, open(out.replace(".png", ".json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
