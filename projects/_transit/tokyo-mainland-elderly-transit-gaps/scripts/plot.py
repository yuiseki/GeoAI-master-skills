"""Draw task 39's fixed-break mesh map with a separate reading panel.

Run from the repository root with the dependencies in README.md.
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.parent.name / PROJECT.name
OUTPUT = PROJECT / "outputs"
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from classify_map import EDGE, assign, breaks, drop_degenerate_holes  # noqa: E402
from cjk_font import use_cjk_font  # noqa: E402

THRESHOLDS = [1, 250, 500, 1000]
PALETTE = "YlOrRd"


def classify(values):
    """Return classes, counts, NoData count and edges; unknown is never zero."""
    import numpy as np

    ok = [v is not None and math.isfinite(float(v)) for v in values]
    known = np.array([float(v) for v, valid in zip(values, ok) if valid])
    if not len(known):
        raise ValueError("no known mesh values")
    edges = breaks(known, "fixed", thresholds=THRESHOLDS)
    selected = assign(known, edges).astype(int).tolist()
    labels = iter(selected)
    classes = [next(labels) if valid else -1 for valid in ok]
    counts = np.bincount(selected, minlength=len(edges) - 1).astype(int).tolist()
    return classes, counts, len(values) - len(known), [int(x) if float(x).is_integer() else float(x) for x in edges]


def polygon_path(poly):
    import numpy as np
    from matplotlib.path import Path as MPath

    rings = [np.asarray(poly.exterior.coords)] + [np.asarray(r.coords) for r in poly.interiors]
    codes = []
    for ring in rings:
        codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(ring) - 2) + [MPath.CLOSEPOLY])
    return MPath(np.concatenate(rings), codes)


def main():
    import duckdb
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, PathPatch
    import numpy as np
    import shapely

    summary = json.loads((OUTPUT / "analysis.json").read_text())
    con = duckdb.connect()
    con.sql("INSTALL spatial; LOAD spatial;")
    rows = con.sql(
        f"SELECT mesh, age65_gap_priority, ST_AsWKB(geometry) "
        f"FROM '{ARTIFACTS / 'map-units.parquet'}' ORDER BY mesh"
    ).fetchall()
    values = [row[1] for row in rows]
    classes, counts, nodata, edges = classify(values)
    geoms = [shapely.from_wkb(bytes(row[2])) for row in rows]
    equal = assign(np.array([v for v in values if v is not None], dtype=float),
                   breaks(np.array([v for v in values if v is not None], dtype=float), "equal", k=5))
    fixed = [c for c in classes if c >= 0]
    changed = float(np.mean(np.array(fixed) != equal))

    labels = ["0–1", "2–250", "251–500", "501–1,000", "1,001以上"]
    title = "東京都本土｜高齢者が多い交通空白候補"
    subtitle = "バス停まで徒歩800m超 かつ 駅まで徒歩1,500m超｜2020年国勢調査3次メッシュ"
    source = "国勢調査2020／P11バス停／駅データ／OSM道路／行政界"
    font = use_cjk_font(" ".join([title, subtitle, source, "人 メッシュ 分類 凡例 NoData 不明 \n"] + labels))

    fig = plt.figure(figsize=(16, 8), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[4.4, 1.45], left=.035, right=.98,
                          top=.82, bottom=.12, wspace=.045)
    ax = fig.add_subplot(gs[0, 0])
    panel = fig.add_subplot(gs[0, 1])
    panel.axis("off")
    cmap = plt.get_cmap(PALETTE, 5)
    seams = 0
    for geom, cls in zip(geoms, classes):
        for poly in getattr(geom, "geoms", [geom]):
            poly, removed = drop_degenerate_holes(poly)
            seams += removed
            ax.add_patch(PathPatch(polygon_path(poly),
                                   facecolor="#d4d7da" if cls < 0 else cmap(cls),
                                   edgecolor=EDGE, linewidth=.28,
                                   hatch="///" if cls < 0 else None))
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")

    for rank, item in enumerate(summary["top10"][:3], start=1):
        ax.scatter(item["lon"], item["lat"], s=115, facecolors="white", edgecolors="#222222",
                   linewidths=1.4, zorder=10)
        ax.text(item["lon"], item["lat"], str(rank), ha="center", va="center", size=8,
                weight="bold", zorder=11)

    fig.text(.035, .955, title, fontsize=19, weight="bold", color="#20252a", ha="left", va="top")
    fig.text(.035, .907, subtitle, fontsize=10, color="#414b53", ha="left", va="top")
    handles = [Patch(facecolor=cmap(i), edgecolor=EDGE,
                     label=f"{labels[i]}人  ({counts[i]}メッシュ)") for i in range(5)]
    handles.append(Patch(facecolor="#d4d7da", edgecolor=EDGE, hatch="///",
                         label=f"NoData  ({nodata}メッシュ)"))
    panel.text(0, .99, "凡例｜条件を満たす65歳以上人数", fontsize=11, weight="bold", va="top")
    panel.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, .93),
                 frameon=False, fontsize=10, handlelength=1.8, labelspacing=1.1, borderaxespad=0)
    panel.text(0, .53, "数字は中心点評価での上位3メッシュ", fontsize=9, va="top")
    for i, item in enumerate(summary["top10"][:3], start=1):
        panel.text(0, .48 - .075 * (i - 1),
                   f"{i}  {item['municipality']}  {item['mesh']}\n     65歳以上 {item['age65']:,}人",
                   fontsize=9, va="top", linespacing=1.35)
    panel.text(0, .16, "注：色は居住者の実際の経路や\n移動困難を直接示すものではありません。",
               fontsize=8.5, color="#51575c", va="top")
    fig.text(.035, .055, source + "｜各スナップショットの版は図と同名のJSON参照", fontsize=9,
             color="#4c5459", va="bottom")
    fig.text(.035, .026, "道路距離：EPSG:6677（m）／地図：JGD2011 3次メッシュ（経緯度）", fontsize=8,
             color="#6b7278", va="bottom")

    metadata = {
        "question": summary["question"], "made": date.today().isoformat(),
        "sources": summary["sources"], "geometry_crs": "JGD2011 3rd mesh longitude/latitude",
        "distance_crs": "EPSG:6677", "unit": "mesh", "value": "age65_gap_priority",
        "definition": "age65 if bus_m > 800 and rail_m > 1500, else 0; unknown is NoData",
        "method": "fixed", "breaks": edges, "legend_labels": labels,
        "units_per_class": counts, "nodata_units": nodata, "total_units": len(rows),
        "fixed_vs_equal_changed_share": changed, "palette": PALETTE,
        "boundary": EDGE, "font": font, "zero_area_rings_left_out": seams,
        "renderer": "project plot.py; classifications/path/font from analysis-visualize skill",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "elderly-transit-gap-map.png"
    fig.savefig(out, dpi=170, metadata={"Description": json.dumps(metadata, ensure_ascii=False)})
    out.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    plt.close(fig)
    print(f"wrote {out}; {len(rows)} meshes, {nodata} NoData, {seams} degenerate holes")


if __name__ == "__main__":
    main()
