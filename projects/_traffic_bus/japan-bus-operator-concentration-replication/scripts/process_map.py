"""Draw how one municipality's share is made: stops, the 800 m test per mesh, classes, and the sum.

uv run --no-project --with duckdb --with numpy --with scipy --with shapely --with matplotlib \
  python3 projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/process_map.py
"""

import csv
import json
import math
import sys
from pathlib import Path

from analysis import ARTIFACTS, EARTH_KM, PROJECT, mesh_center, url

ROOT = PROJECT.parents[2]
CODE5 = "01207"
NAME = "帯広市"
RADIUS = 800
WINDOW_KM = 1.5
CLASS_COLORS = {"2+": "#7570b3", "1": "#d95f02", "0": "#cccccc", "out": "#ffffff"}
CLASS_NAMES = {"2+": "事業者名 2 種類以上", "1": "事業者名 1 種類", "0": "停留所なし (分母の外)", "out": "65 歳以上が秘匿か 0 人 (外す)"}
OPERATOR_COLORS = {"十勝バス（株）": "#1b9e77", "北海道拓殖バス（株）": "#e6ab02"}
OTHER_OPERATOR = "#666666"


def mesh_square(code):
    lon, lat = mesh_center(code)
    return lon - 1 / 160, lat - 1 / 240, lon + 1 / 160, lat + 1 / 240


def mesh_class(operators, age65):
    if age65 is None or age65 <= 0:
        return "out"
    return "0" if operators == 0 else "1" if operators == 1 else "2+"


def pick_examples(rows):
    """The mesh with the most people aged 65+ in each of the classes 2+, 1, 0."""
    picked = []
    for cls in ("2+", "1", "0"):
        found = [r for r in rows if mesh_class(r["operators_800m"], r["age65"]) == cls]
        if not found:
            raise ValueError(f"no mesh in class {cls}")
        picked.append(max(found, key=lambda r: (r["age65"], r["mesh_code"])))
    return picked


def meters(lon0, lat0, lon, lat):
    a, b = math.radians(lat0), math.radians(lat)
    h = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(lon - lon0) / 2) ** 2
    return 2000 * EARTH_KM * math.asin(min(1, math.sqrt(h)))


def stops_within(lon, lat, stops, radius):
    return [s for s in stops if meters(lon, lat, s[1], s[2]) <= radius]


def circle_lonlat(lon, lat, radius, n=128):
    d = radius / 1000 / EARTH_KM
    a, b = math.radians(lat), math.radians(lon)
    out = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        y = math.asin(math.sin(a) * math.cos(d) + math.cos(a) * math.sin(d) * math.cos(t))
        x = b + math.atan2(math.sin(t) * math.sin(d) * math.cos(a), math.cos(d) - math.sin(a) * math.sin(y))
        out.append((math.degrees(x), math.degrees(y)))
    return out


def load_meshes():
    rows = []
    with (ARTIFACTS / "meshes.csv").open(encoding="utf-8", newline="") as stream:
        for r in csv.DictReader(stream):
            rows.append({
                "mesh_code": r["mesh_code"], "lon": float(r["longitude"]), "lat": float(r["latitude"]),
                "age65": None if r["age65"] in ("", "None") else int(r["age65"]),
                "code5": r["municipality_code"], "operators_800m": int(r["operators_800m"]),
            })
    return rows


def main():
    import duckdb
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Polygon, Rectangle
    from shapely import box as shapely_box, wkb

    sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
    from cjk_font import use_cjk_font
    from context_map import text_overlaps

    meshes = load_meshes()
    city = [r for r in meshes if r["code5"] == CODE5]
    with (PROJECT / "outputs/municipalities.csv").open(encoding="utf-8", newline="") as stream:
        summary = next(r for r in csv.DictReader(stream) if r["code5"] == CODE5)
    audit = json.loads((PROJECT / "outputs/audit.json").read_text(encoding="utf-8"))["radii"][str(RADIUS)]
    counts = {c: sum(mesh_class(r["operators_800m"], r["age65"]) == c for r in city) for c in CLASS_COLORS}
    pop = {c: sum(r["age65"] for r in city if mesh_class(r["operators_800m"], r["age65"]) == c) for c in ("2+", "1", "0")}
    if counts["1"] != int(summary["single_meshes"]) or counts["1"] + counts["2+"] != int(summary["stop_meshes"]):
        raise ValueError(f"mesh classes do not match municipalities.csv: {counts}")
    if pop["1"] != int(summary["single_older_population"]) or pop["1"] + pop["2+"] != int(summary["stop_older_population"]):
        raise ValueError(f"populations do not match municipalities.csv: {pop}")
    examples = pick_examples(city)

    xs = [r["lon"] for r in city]
    ys = [r["lat"] for r in city]
    view = (min(xs) - 0.03, max(xs) + 0.03, min(ys) - 0.03, max(ys) + 0.03)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial")
    cache = ARTIFACTS / f"stops_{CODE5}.parquet"
    if not cache.exists():
        con.execute(
            f"COPY (SELECT name, operator, ST_X(geometry) x, ST_Y(geometry) y FROM read_parquet(?) "
            f"WHERE ST_X(geometry) BETWEEN {view[0] - 0.05} AND {view[1] + 0.05} "
            f"AND ST_Y(geometry) BETWEEN {view[2] - 0.05} AND {view[3] + 0.05}) TO '{cache}' (FORMAT PARQUET)",
            [url("stops")],
        )
    stops = [(op, x, y, name) for name, op, x, y in con.execute(f"SELECT name, operator, x, y FROM '{cache}'").fetchall()]
    admin = con.execute(
        f"SELECT code5, name, ST_AsWKB(geometry) FROM read_parquet(?) WHERE ward IS NULL AND geometry IS NOT NULL "
        f"AND ST_Intersects(geometry, ST_MakeEnvelope({view[0]}, {view[2]}, {view[1]}, {view[3]}))",
        [url("admin")],
    ).fetchall()
    for r in examples:
        inside = stops_within(r["lon"], r["lat"], stops, RADIUS)
        if len({s[0] for s in inside}) != r["operators_800m"]:
            raise ValueError(f"stop cache disagrees with meshes.csv at {r['mesh_code']}")
        r["inside"] = inside

    def nearest_stop(r):
        return min(stops, key=lambda s: meters(r["lon"], r["lat"], s[1], s[2]))[3]

    labels = [f"{NAME}", "音更町", "芽室町", "幕別町", "中札内村", "更別村", "十勝バス（株）", "北海道拓殖バス（株）", "そのほかの事業者"]
    labels += list(CLASS_NAMES.values()) + [nearest_stop(r) for r in examples]
    use_cjk_font("".join(labels) + "①②③④入力判定分類集計メッシュ中心からの半径 m 停留所 65 歳以上人口 人 割合 全国 % 種類 の近く (行政界) 1km 経緯度 JGD 版 P11 2022 国勢調査 2020 行政界の固定版 ×")

    lat0 = math.radians((view[2] + view[3]) / 2)
    fig = plt.figure(figsize=(13, 21))
    grid = fig.add_gridspec(2, 2, width_ratios=[1, 0.5], hspace=0.12, wspace=0.08)
    ax_in = fig.add_subplot(grid[0, 0])
    ax_cls = fig.add_subplot(grid[1, 0])
    ax_sum = fig.add_subplot(grid[1, 1])
    sub = grid[0, 1].subgridspec(3, 1, hspace=0.45)
    small = [fig.add_subplot(sub[i]) for i in range(3)]

    texts = []

    def draw_admin(ax, emphasize=True, label=True):
        for code5, name, geom in admin:
            shape = wkb.loads(geom)
            polys = getattr(shape, "geoms", [shape])
            for p in polys:
                x, y = p.exterior.xy
                ax.plot(x, y, color="#222222" if code5 == CODE5 and emphasize else "#888888",
                        lw=1.6 if code5 == CODE5 and emphasize else 0.6, zorder=5)
            if label:
                c = shape.intersection(shapely_box(view[0], view[2], view[1], view[3]))
                if c.is_empty or c.area < 0.004:
                    continue
                pt = c.representative_point()
                t = ax.text(pt.x, pt.y, name, ha="center", va="center", fontsize=10 if code5 == CODE5 else 8.5,
                            color="#111111", zorder=8, bbox=dict(facecolor="white", alpha=0.75, lw=0, pad=1.2))
                texts.append(t)

    def frame(ax, box):
        ax.set_xlim(box[0], box[1])
        ax.set_ylim(box[2], box[3])
        ax.set_aspect(1 / math.cos(lat0))
        ax.set_xticks([])
        ax.set_yticks([])

    def operator_color(op):
        return OPERATOR_COLORS.get(op, OTHER_OPERATOR)

    # ① 入力
    vmax = max(r["age65"] or 0 for r in meshes if view[0] <= r["lon"] <= view[1] and view[2] <= r["lat"] <= view[3])
    cmap = plt.get_cmap("Greys")
    for r in meshes:
        if not (view[0] - 0.01 <= r["lon"] <= view[1] + 0.01 and view[2] - 0.01 <= r["lat"] <= view[3] + 0.01):
            continue
        x0, y0, x1, y1 = mesh_square(r["mesh_code"])
        face = "#f4f4f4" if r["age65"] is None else cmap(0.08 + 0.5 * math.sqrt(r["age65"] / vmax))
        ax_in.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=face, edgecolor="white", lw=0.3, zorder=1))
    for op, x, y, _ in stops:
        ax_in.plot(x, y, "o", ms=2.2, color=operator_color(op), zorder=6, mec="none")
    draw_admin(ax_in)
    frame(ax_in, view)
    ax_in.set_title("① 入力: 1km メッシュの 65 歳以上人口 (灰の濃さ) と\n停留所 (事業者名ごとの色)", fontsize=12, loc="left")
    ax_in.legend(handles=[Line2D([], [], marker="o", ls="", color=c, label=k) for k, c in OPERATOR_COLORS.items()]
                 + [Line2D([], [], marker="o", ls="", color=OTHER_OPERATOR, label="そのほかの事業者")],
                 loc="upper left", bbox_to_anchor=(0, -0.01), ncol=3, fontsize=9, frameon=False)

    # ② 判定
    marks = "ABC"
    for i, (ax, r) in enumerate(zip(small, examples)):
        half_lat = math.degrees(WINDOW_KM / EARTH_KM)
        half_lon = half_lat / math.cos(math.radians(r["lat"]))
        box = (r["lon"] - half_lon, r["lon"] + half_lon, r["lat"] - half_lat, r["lat"] + half_lat)
        for m in meshes:
            if abs(m["lon"] - r["lon"]) < 0.04 and abs(m["lat"] - r["lat"]) < 0.03:
                x0, y0, x1, y1 = mesh_square(m["mesh_code"])
                ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="none", edgecolor="#bbbbbb", lw=0.5, zorder=1))
        x0, y0, x1, y1 = mesh_square(r["mesh_code"])
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=CLASS_COLORS[mesh_class(r["operators_800m"], r["age65"])],
                               alpha=0.25, edgecolor="#222222", lw=1.2, zorder=2))
        ax.add_patch(Polygon(circle_lonlat(r["lon"], r["lat"], RADIUS), closed=True, fill=False, ls="--", lw=1.2, color="#222222", zorder=4))
        ax.plot(r["lon"], r["lat"], "x", color="#222222", ms=7, mew=1.6, zorder=6)
        inside = {(s[1], s[2]) for s in r["inside"]}
        for op, x, y, _ in stops:
            if box[0] <= x <= box[1] and box[2] <= y <= box[3]:
                hit = (x, y) in inside
                ax.plot(x, y, "o", ms=5 if hit else 3, color=operator_color(op), alpha=1 if hit else 0.35,
                        mec="#222222" if hit else "none", mew=0.5, zorder=5)
        frame(ax, box)
        cls = mesh_class(r["operators_800m"], r["age65"])
        ops = sorted({s[0] for s in r["inside"]})
        what = "、".join(o.replace("（株）", "") for o in ops) if ops else "停留所なし"
        ax.set_title(f"{marks[i]} {nearest_stop(r)} の近く: 65 歳以上 {r['age65']:,} 人\n半径 {RADIUS} m の中は {what}\n→ {CLASS_NAMES[cls]}",
                     fontsize=9.5, loc="left")
    small[0].text(0, 1.38, "② 判定: メッシュ中心 (×) から\n半径 800 m の停留所の事業者名を数える",
                  transform=small[0].transAxes, fontsize=12, va="bottom")

    # ③ 分類
    for r in meshes:
        if not (view[0] - 0.01 <= r["lon"] <= view[1] + 0.01 and view[2] - 0.01 <= r["lat"] <= view[3] + 0.01):
            continue
        x0, y0, x1, y1 = mesh_square(r["mesh_code"])
        cls = mesh_class(r["operators_800m"], r["age65"])
        mine = r["code5"] == CODE5
        ax_cls.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=CLASS_COLORS[cls], alpha=1 if mine else 0.18,
                                   edgecolor="#999999" if cls == "out" else "white", hatch="///" if cls == "out" and mine else None,
                                   lw=0.3, zorder=1))
    for i, r in enumerate(examples):
        t = ax_cls.text(r["lon"], r["lat"], marks[i], ha="center", va="center", fontsize=12, zorder=9,
                        bbox=dict(boxstyle="circle,pad=0.15", facecolor="white", edgecolor="#222222", lw=0.8))
        texts.append(t)
    draw_admin(ax_cls)
    frame(ax_cls, view)
    ax_cls.set_title(f"③ 分類: {NAME}に割り当てたメッシュ (中心が市の面に入る {len(city)} 件)\n他の市町村のメッシュは薄く描いた", fontsize=12, loc="left")
    ax_cls.legend(handles=[Patch(facecolor=CLASS_COLORS[c], edgecolor="#999999", hatch="///" if c == "out" else None,
                                 label=f"{CLASS_NAMES[c]} ({counts[c]})") for c in ("2+", "1", "0", "out")],
                  loc="upper left", bbox_to_anchor=(0, -0.01), ncol=2, fontsize=9, frameon=False)

    # ④ 集計
    rows = [(NAME, pop["1"], pop["2+"]), ("全国", audit["single_older_population"],
            audit["stop_older_population"] - audit["single_older_population"])]
    for j, (name, one, more) in enumerate(rows):
        total = one + more
        ax_sum.bar(j, 100 * one / total, color=CLASS_COLORS["1"], width=0.7)
        ax_sum.bar(j, 100 * more / total, bottom=100 * one / total, color=CLASS_COLORS["2+"], width=0.7)
        ax_sum.text(j, 100 * one / total / 2, f"1 種類\n{100 * one / total:.1f}%\n{one:,} 人", ha="center", va="center", color="white", fontsize=10.5)
        ax_sum.text(j, 100 * one / total + 100 * more / total / 2, f"2 種類以上\n{more:,} 人", ha="center", va="center", color="white", fontsize=10.5)
    ax_sum.set_xticks([0, 1], [r[0] for r in rows], fontsize=11)
    ax_sum.set_ylim(0, 100)
    ax_sum.yaxis.tick_right()
    ax_sum.yaxis.set_label_position("right")
    ax_sum.set_ylabel("停留所が半径 800 m にあるメッシュの\n65 歳以上人口に占める割合 (%)")
    ax_sum.set_title(f"④ 集計: 人数を足してから割る\n停留所なし ({NAME} {pop['0']:,} 人、\n全国 {audit['no_stop_older_population']:,} 人) は分母に入れない",
                     fontsize=12, loc="left")
    for s in ("top", "left"):
        ax_sum.spines[s].set_visible(False)

    source = "P11 2022 (442223b)・国勢調査 2020 1km メッシュ (6c486c8)・行政界の固定版 (e6c87b1)。経緯度で描き縦を 1/cos(緯度) 倍。距離は球面の大円距離"
    fig.text(0.01, 0.075, source, fontsize=8.5, color="#444444")
    fig.suptitle(f"{NAME}の例: 事業者名が 1 種類のメッシュの 65 歳以上の割合ができるまで", fontsize=15, x=0.01, ha="left", y=0.965)
    overlaps = text_overlaps(fig, texts)
    out = PROJECT / "outputs/process-obihiro.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    meta = {
        "question": f"{NAME}で、事業者名 1 種類の割合はどの手順で決まるか",
        "kind": "diagnostic (method illustration)",
        "reads": ["artifacts/.../meshes.csv", "outputs/municipalities.csv", "outputs/audit.json"],
        "datasets": {k: url(k) for k in ("stops", "census", "admin")},
        "municipality": {"code5": CODE5, "name": NAME, "meshes": len(city), "classes": counts, "older_population": pop},
        "examples": [{"mesh_code": r["mesh_code"], "age65": r["age65"], "operators_800m": r["operators_800m"],
                      "near": nearest_stop(r), "operators": sorted({s[0] for s in r["inside"]})} for r in examples],
        "example_rule": "各分類で 65 歳以上が最も多いメッシュ",
        "stops_drawn": len(stops),
        "crs": "経緯度 (P11 EPSG:6668、行政界 EPSG:4612。差は線の幅より小さい)",
        "aspect": f"1/cos({math.degrees(lat0):.3f})",
        "text_overlaps": overlaps,
        "font": plt.rcParams["font.family"],
    }
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
