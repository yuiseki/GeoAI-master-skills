"""Draw the figures of the Minato accident reports from outputs/*.csv and the artifacts.

Run from repository root after analyze.py:
uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib \
  python projects/_traffic_accident/minato-accident-trends-by-role/scripts/plot.py
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Circle, Patch, Rectangle
from shapely import wkb

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
ART = ROOT / "artifacts/_traffic_accident/minato-accident-trends-by-role"
OUT = PROJECT / "outputs"
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font
from context_map import text_overlaps

CRS_NOTE = {"map_crs": "EPSG:6677", "background": "roads OGC:CRS84, ward and towns EPSG:4612",
            "accepted_difference": "JGD2000 と WGS84 の差 (約 1 m) は道路の線の幅より小さい"}
NUMBER_BOX = dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9)

SOURCE = ("出所: 警察庁「交通事故統計のオープンデータ」2019-2025年 (yuiseki/npa-traffic-accidents@389500a) より加工。"
          "背景: OpenStreetMap 2026-08-31 (osm-tokyo23-src@38f7a5f)、令和2年国勢調査 (estat-boundary-2020@823195c)")
LANDMARKS = {
    "新橋": "新橋一丁目", "赤坂": "赤坂一丁目", "六本木": "六本木六丁目", "麻布十番": "麻布十番一丁目",
    "芝": "芝五丁目", "白金台": "白金台一丁目", "高輪": "高輪三丁目", "虎ノ門": "虎ノ門一丁目",
    "台場": "台場一丁目", "芝浦": "芝浦三丁目", "南青山": "南青山三丁目"
}
MAJOR = {"motorway", "trunk", "primary", "secondary", "trunk_link", "primary_link"}
WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"]
TEXT = ("0123456789,.%()/-|~・:年市区港23全自転車歩行者高齢若い道路幹線一般特定小型原付"
        "世帯あたり男女学校事故死傷千台新橋赤坂六本木麻布十番芝白金台高輪虎ノ門台場芝浦南青山図出所警察庁交通事故オープンデータ加工背景"
        "地図地点前後AB乗用貨物二輪なしその他南北東西以上未満との交差点手前信号停止横断歩道"
        "夜間早朝夕方深夜昼間平日休日95%Poissonの範囲指数推移割合時間帯別件数構成"
        "レポートパイプライン結び付き関係内訳単位速度超過重症軽傷死亡発見同乗当事者第"
        "通過進行右折左折直進追突出会頭正面衝突施設距離規模分布過半数約倍比率"
        "鳥居坂泉霞町陸橋榎坂昭和中央第一京浜桜田外堀国道246海岸なぎさ日比谷四谷角筈青山外苑詳細位置スケールバーOSMの道路のみを細く7年計Weekday土日")


def read_csv(name):
    with (OUT / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(fig, name, question, inputs, n, notes="", checks=None):
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    meta = {"question": question, "inputs": inputs, "n": n, "notes": notes, "source": SOURCE,
            "font": plt.rcParams["font.family"], **(checks or {})}
    (OUT / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", path.relative_to(ROOT))


class Base:
    """Ward outline, roads and landmark names in EPSG:6677."""

    def __init__(self):
        con = duckdb.connect()
        con.sql("load spatial")
        con.sql("set geometry_always_xy = true")
        tr = "ST_AsWKB(ST_Transform(ST_GeomFromWKB(geometry), '{}', 'EPSG:6677'))"
        self.ward = wkb.loads(con.execute(f"select {tr.format('EPSG:4612')} from '{(ART / 'wards.parquet').as_posix()}' "
                                          "where code5 = '13103'").fetchall()[0][0])
        self.roads = [(h, wkb.loads(g)) for h, g in con.execute(
            f"select highway, {tr.format('OGC:CRS84')} from '{(ART / 'roads.parquet').as_posix()}'").fetchall()]
        self.towns = {n: (wkb.loads(g), wkb.loads(g2)) for n, g, g2 in con.execute(
            f"select S_NAME, {tr.format('EPSG:4612')}, ST_AsWKB(ST_GeomFromWKB(geometry)) from '{(ART / 'towns.parquet').as_posix()}'").fetchall()}
        with (ART / "points.csv").open(encoding="utf-8") as f:
            self.points = [{k: (v == "True" if v in ("True", "False") else float(v) if k in ("x", "y") else int(v)
                                if k in ("weekday", "hour") else v) for k, v in r.items()} for r in csv.DictReader(f)]
        self.schools = con.execute(f"""select name,
            ST_X(ST_Transform(ST_Point(lon, lat), 'OGC:CRS84', 'EPSG:6677')),
            ST_Y(ST_Transform(ST_Point(lon, lat), 'OGC:CRS84', 'EPSG:6677')) from '{(ART / 'schools.parquet').as_posix()}'""").fetchall()

    def point_rows(self):
        return self.points

    def draw(self, ax, extent=None, labels=True, road_alpha=1.0, skip=()):
        for h, g in self.roads:
            lines = getattr(g, "geoms", [g])
            for line in lines:
                x, y = line.xy
                ax.plot(x, y, color="#9a9a9a" if h in MAJOR else "#d4d4d4", lw=1.1 if h in MAJOR else 0.4,
                        alpha=road_alpha, zorder=1, solid_capstyle="round")
        for poly in getattr(self.ward, "geoms", [self.ward]):
            x, y = poly.exterior.xy
            ax.plot(x, y, color="#333333", lw=1.2, zorder=2)
        if extent is None:
            xmin, ymin, xmax, ymax = self.ward.bounds
            pad = 200
            extent = (xmin - pad, xmax + pad, ymin - pad, ymax + pad)
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        texts = []
        if labels:
            for label, town in LANDMARKS.items():
                if label in skip or town not in self.towns:
                    continue
                p = self.towns[town][0].representative_point()
                if extent[0] < p.x < extent[1] and extent[2] < p.y < extent[3]:
                    texts.append(ax.text(p.x, p.y, label, fontsize=8, color="#222222", ha="center", va="center",
                                         zorder=6, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7)))
        self.scalebar(ax, extent)
        return texts

    @staticmethod
    def scalebar(ax, extent, length=1000):
        x0 = extent[0] + 0.05 * (extent[1] - extent[0])
        y0 = extent[2] + 0.04 * (extent[3] - extent[2])
        length = 1000 if extent[1] - extent[0] > 3000 else 200
        ax.add_patch(Rectangle((x0, y0), length, 0.006 * (extent[3] - extent[2]), color="black", zorder=7))
        ax.text(x0 + length / 2, y0 + 0.015 * (extent[3] - extent[2]), f"{length} m", ha="center", fontsize=8, zorder=7)
        ax.text(extent[1] - 0.04 * (extent[1] - extent[0]), extent[3] - 0.05 * (extent[3] - extent[2]), "北",
                ha="center", fontsize=9, weight="bold", zorder=7)


def fig_trend():
    rows = read_csv("yearly.csv")
    years = sorted(set(int(r["year"]) for r in rows))
    fig, ax = plt.subplots(figsize=(7, 4))
    for scope, color in (("港区", "#c0392b"), ("23区", "#555555")):
        rs = [r for r in rows if r["scope"] == scope]
        base = next(int(r["accidents"]) for r in rs if int(r["year"]) == 2019)
        idx = [int(r["accidents"]) / base * 100 for r in rs]
        ax.plot(years, idx, marker="o", color=color, label=f"{scope} (2019年={base:,}件を100)")
        lo = [(int(r["accidents"]) - 1.96 * np.sqrt(int(r["accidents"]))) / base * 100 for r in rs]
        hi = [(int(r["accidents"]) + 1.96 * np.sqrt(int(r["accidents"]))) / base * 100 for r in rs]
        ax.fill_between(years, lo, hi, color=color, alpha=0.12)
    ax.axhline(100, color="#888888", ls="--", lw=0.7)
    ax.set_ylim(60, 120)
    ax.set_ylabel("事故件数の指数 (2019年 = 100)")
    ax.set_title("港区と23区の人身事故の件数の推移", fontsize=11)
    ax.text(0, -0.2, "帯: 各年の件数にPoisson 95%区間を置き指数に換算。" + SOURCE[:40] + "…", transform=ax.transAxes, fontsize=7)
    ax.legend(loc="lower right", fontsize=9)
    save(fig, "trend-index", "港区の事故の件数は23区全体と比べてどう動いたか", ["outputs/yearly.csv"],
         {r["scope"]: sum(int(x["accidents"]) for x in rows if x["scope"] == r["scope"]) for r in rows},
         "2019年を100とした推移。2020年の落ち込みから2023-2024年にかけての戻り方を比較")


def fig_categories():
    rows = [r for r in read_csv("yearly.csv") if r["scope"] == "港区"]
    years = [int(r["year"]) for r in rows]
    panels = [("bike", "自転車が関わる"), ("ped", "歩行者が関わる"), ("old_ped", "高齢 (65歳以上) の歩行者が関わる"),
              ("young_pb", "若い (0〜24歳) 歩行者・自転車が関わる"), ("strict", "幹線道路 (厳密 / 広義)"),
              ("escooter", "特定小型原付 (電動キックボード等) が関わる")]
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.6), sharex=True)
    for ax, (key, title) in zip(axes.flat, panels):
        ax.plot(years, [int(r[key]) for r in rows], marker="o", color="#c0392b", label="厳密" if key == "strict" else None)
        if key == "strict":
            ax.plot(years, [int(r["broad"]) for r in rows], marker="s", color="#2c7fb8", label="広義")
            ax.legend(fontsize=8, loc="lower left")
        ax.set_ylim(0, None)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("件", fontsize=9)
        ax.grid(axis="y", color="#eeeeee")
    fig.suptitle("港区の人身事故のうち、当事者や道路の種類ごとの件数 (年)", fontsize=11)
    fig.text(0.01, -0.01, "当事者A・Bのどちらか当てはまる事故の件数を1と数えた。特定小型原付は2024年からの区分。" + SOURCE[:46] + "…",
             fontsize=7)
    fig.tight_layout()
    save(fig, "minato-categories", "港区で、どの種類の事故が年ごとにどう動いたか", ["outputs/yearly.csv"],
         sum(int(r["accidents"]) for r in rows), "特定小型原付は2023年以前は0。パネルごとに縦の範囲は違う")


def fig_ward_strips():
    rows = read_csv("wards.csv")
    cols = [("per_1000_residents_per_year", "住民千人あたり年件数", "件/千人/年", True),
            ("share_ped", "歩行者事故の割合", "%", False),
            ("share_bike", "自転車事故の割合", "%", False),
            ("share_escooter", "特定小型原付事故の割合 (2024-2025)", "%", False),
            ("share_night", "夜間 (18〜5時) の割合", "%", False),
            ("share_intersection", "交差点事故の割合", "%", False),
            ("share_strict", "幹線道路 (厳密) の割合", "%", False)]
    fig, axes = plt.subplots(len(cols), 1, figsize=(8.5, 7.8), sharex=False)
    for ax, (key, label, unit, is_rate) in zip(axes, cols):
        vals = [(float(r[key]), r["name"]) for r in rows]
        xs = [v for v, _ in vals]
        ax.scatter([v for v, n in vals if n != "港区"], [0] * 22, color="#9a9a9a", s=22, zorder=2)
        target = next(v for v, n in vals if n == "港区")
        ax.scatter([target], [0], color="#c0392b", s=60, zorder=3)
        rank = 1 + sum(v > target for v in xs)
        ax.text(target, 0.45, f"港区 {target:.1f} ({rank}位/23)", color="#c0392b", fontsize=8, ha="center")
        for v, n in vals:
            if v in (max(xs), min(xs)) and n != "港区":
                ax.text(v, -0.6, n, fontsize=7, ha="center", color="#555555")
        ax.set_yticks([])
        ax.set_ylabel(label, fontsize=8, rotation=0, labelpad=75, ha="right", va="center")
        for spine in ("left", "right", "top"):
            ax.spines[spine].set_visible(False)
        lo, hi = min(xs), max(xs)
        ax.set_xlim(lo - 0.08 * (hi - lo), hi + 0.08 * (hi - lo))
    fig.suptitle("23区の中の港区 (2019〜2025年の7年計の構成)", fontsize=11)
    fig.text(0.01, -0.01, "灰色の点はほかの22区。赤は港区の値。住民千人あたり件数は2020年の夜間人口で割った参考値。" + SOURCE[:46] + "…",
             fontsize=7)
    fig.tight_layout()
    save(fig, "ward-strips", "港区の事故の構成は、23区の中でどこにあるか", ["outputs/wards.csv"],
         sum(int(r["accidents"]) for r in rows), "各行で横の範囲は違う。0から始まらない (区の位置を並べる図)")


def fig_hours():
    rows = read_csv("hour_weekday.csv")
    groups = [("全体", "すべての事故"), ("若い歩行者・自転車", "若い (0〜24歳) 歩行者・自転車が関わる事故")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.6))
    ns = {}
    for ax, (g, title) in zip(axes, groups):
        m = np.zeros((7, 24))
        for r in rows:
            if r["group"] == g:
                m[int(r["weekday"]) - 1, int(r["hour"])] = int(r["accidents"])
        order = [1, 2, 3, 4, 5, 6, 0]
        im = ax.imshow(m[order], aspect="auto", cmap="YlOrRd", vmin=0)
        ax.set_yticks(range(7), [WEEKDAYS[i] for i in order])
        ax.set_xticks(range(0, 24, 3), [f"{h}時" for h in range(0, 24, 3)])
        ax.set_title(f"{title} (n={int(m.sum()):,})", fontsize=10)
        cb = fig.colorbar(im, ax=ax, shrink=0.85)
        cb.set_label("件 (7年計)", fontsize=8)
        ns[g] = int(m.sum())
    fig.suptitle("港区の人身事故の曜日と時間帯 (2019〜2025年)", fontsize=11)
    fig.text(0.01, -0.03, "パネルごとに色の範囲は違う。横軸は時間 (0〜23時)。" + SOURCE[:46] + "…", fontsize=7)
    fig.tight_layout()
    save(fig, "hour-weekday", "港区の事故は何曜日の何時に多いか。若い歩行者と自転車では違うか",
         ["outputs/hour_weekday.csv"], ns, "色の範囲は各パネル別")


def fig_hour_profile():
    rows = read_csv("hour_weekday.csv")
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for g, color in (("自転車", "#2c7fb8"), ("全体", "#555555"), ("高齢歩行者", "#c0392b")):
        c = defaultdict(int)
        for r in rows:
            if r["group"] == g:
                c[int(r["hour"])] += int(r["accidents"])
        ax.plot(range(24), [c[h] for h in range(24)], marker="o", ms=3, color=color, label=f"{g} (n={sum(c.values()):,})")
    ax.set_xticks(range(0, 24, 3), [f"{h}時" for h in range(0, 24, 3)])
    ax.set_ylim(0, None)
    ax.set_ylabel("件 (7年計)")
    ax.set_xlabel("時")
    ax.legend(fontsize=9)
    ax.grid(axis="y", color="#eeeeee")
    ax.set_title("港区の人身事故の時間帯 (2019〜2025年、すべての曜日)", fontsize=11)
    save(fig, "hour-profile", "日のどの時間帯に、どんな人に関わる事故が多いか", ["outputs/hour_weekday.csv"], None,
         "高齢歩行者は夜間にも発生するが昼間に山があり、全体では夜間も高い水準を維持")


def fig_school_map(base):
    pts = [p for p in base.point_rows() if p["young_pb"]]
    schools = read_csv("schools.csv")
    fig, ax = plt.subplots(figsize=(8, 8))
    texts = base.draw(ax)
    xy = {n: (x, y) for n, x, y in base.schools}
    for s in schools:
        if s["school"] not in xy:
            continue
        x, y = xy[s["school"]]
        ax.add_patch(Circle((x, y), 500, fill=False, ec="#2c7fb8", lw=0.6, alpha=0.6, zorder=3))
        ax.plot(x, y, marker="s", color="#2c7fb8", ms=5, zorder=5)
    weekday_peak = [p for p in pts if 2 <= p["weekday"] <= 6 and (7 <= p["hour"] <= 8 or 14 <= p["hour"] <= 17)]
    other = [p for p in pts if p not in weekday_peak]
    ax.scatter([p["x"] for p in other], [p["y"] for p in other], s=7, color="#f39c12", alpha=0.7, zorder=4,
               label=f"その他の時間 ({len(other)}件)")
    ax.scatter([p["x"] for p in weekday_peak], [p["y"] for p in weekday_peak], s=12, color="#c0392b", zorder=4,
               label=f"平日 7〜8時・14〜17時 ({len(weekday_peak)}件)")
    ax.legend(handles=[ax.collections[0], ax.collections[1],
                       plt.Line2D([], [], marker="s", color="#2c7fb8", ls="", label=f"小・中学校 ({len(schools)}校、OSM)"),
                       Patch(fc="none", ec="#2c7fb8", label="学校から半径 500 m")], loc="upper left",
              bbox_to_anchor=(1.0, 1.0), fontsize=8)
    overlaps = text_overlaps(fig, texts, [ax.get_legend()])
    ax.set_title("若い (0〜24歳) 歩行者・自転車が関わる事故と学校 (港区、2019〜2025年)", fontsize=10)
    fig.text(0.01, 0.01, SOURCE, fontsize=6, wrap=True)
    save(fig, "school-map", "学校の近くで、若い歩行者と自転車の事故はどこで起きているか",
         ["artifacts/_traffic_accident/minato-accident-trends-by-role/points.csv", "outputs/schools.csv"],
         {"young_ped_or_bike": len(pts), "weekday_7_8_or_14_17": len(weekday_peak)},
         "0〜24歳は年齢の最小の区分で、通学のみではない。円は直線距離",
         {**CRS_NOTE, "schools_drawn": len(schools), "text_overlaps": overlaps})


def fig_hotspots(base):
    hot = read_csv("hotspots.csv")
    pts = base.point_rows()
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.2), gridspec_kw={"width_ratios": [1, 1]})
    # Zoom covers Aoyama, Roppongi, Akasaka cluster
    zoom = (-11200, -7800, -38300, -35600)
    texts = {0: [], 1: []}
    zoomed = []
    for i, ax in enumerate(axes):
        if i == 0:
            texts[0] += base.draw(ax)
        else:
            base.draw(ax, extent=zoom, labels=False)
        ax.scatter([p["x"] for p in pts], [p["y"] for p in pts], s=1.5 if i == 0 else 4, color="#555555", alpha=0.3,
                   zorder=3, lw=0)
        for h in hot:
            x, y, n = float(h["x"]), float(h["y"]), int(h["accidents"])
            inside = zoom[0] < x < zoom[1] and zoom[2] < y < zoom[3]
            if inside or i == 0:
                ax.add_patch(Circle((x, y), 30, fc="#c0392b", ec="#7b241c", alpha=min(0.9, 0.35 + 0.008 * n), zorder=4))
            if (i == 1 and inside) or (i == 0 and not inside):
                dx, dy = (45, 25) if i else (60, 40)
                texts[i].append(ax.text(x + dx, y + dy, h["rank"],
                                        fontsize=8 if i == 0 else 10, color="#7b241c", weight="bold", zorder=6,
                                        bbox=NUMBER_BOX))
            elif i == 0:
                zoomed.append(int(h["rank"]))
        if i == 0:
            ax.add_patch(Rectangle((zoom[0], zoom[2]), zoom[1] - zoom[0], zoom[3] - zoom[2], fill=False, ec="#2c7fb8",
                                   lw=1.2, ls="--", zorder=6))
    axes[0].set_title(f"港区の人身事故 {len(pts):,}件 (灰色の点) と、事故の多い地点の上位15 (赤い円、半径30 m)", fontsize=10)
    axes[1].set_title("主要ホットスポット群の拡大 (青破線の枠内)", fontsize=10)
    fig.text(0.01, 0.01, "地点は、半径30 mの円の中の7年の事故件数順に、重ならないように選んだ。番号は順位。" + SOURCE,
             fontsize=7, wrap=True)
    overlaps = text_overlaps(fig, texts[0]) + text_overlaps(fig, texts[1])
    save(fig, "hotspots-map", "港区で事故が集まる地点はどこか",
         ["artifacts/_traffic_accident/minato-accident-trends-by-role/points.csv", "outputs/hotspots.csv"], len(pts),
         "位置の精度は不詳。円の濃さは件数に比例",
         {**CRS_NOTE, "hotspots_drawn": len(hot), "zoomed_in_inset": zoomed, "text_overlaps": overlaps})


def fig_hotspot_halves():
    hot = read_csv("hotspots.csv")
    fig, ax = plt.subplots(figsize=(8, 5.2))
    for i, h in enumerate(hot):
        y = len(hot) - i
        a, b = float(h["first_per_year"]), float(h["second_per_year"])
        ax.plot([a, b], [y, y], color="#bbbbbb", zorder=1)
        ax.scatter([a], [y], color="#2c7fb8", zorder=2, label="2019〜2021年 (年平均)" if i == 0 else None)
        ax.scatter([b], [y], color="#c0392b", zorder=2, label="2022〜2025年 (年平均)" if i == 0 else None)
        name = h["road_1"] + (f" × {h['road_2']}" if h["road_2"] and float(h["road_2_m"]) <= 30 else "")
        ax.text(-0.3, y, f"{h['rank']}. {name}", ha="right", va="center", fontsize=8)
    ax.set_yticks([])
    ax.set_xlim(0, None)
    ax.set_xlabel("半径30 m の中の人身事故 (件/年)")
    ax.legend(fontsize=8, loc="lower right")
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    ax.set_title("港区の事故多発地点の上位15: 前半 (2019〜2021) と後半 (2022〜2025) の年平均件数", fontsize=10)
    fig.tight_layout()
    save(fig, "hotspot-halves", "事故の多い地点は、前半と後半でどう動いたか", ["outputs/hotspots.csv"], len(hot),
         "上位地点の多くで後半にかけて減少傾向がみられるが、依然として高水準な交差点も残る")


def fig_party_matrix():
    rows = read_csv("party_matrix.csv")
    order = ["乗用車 (自家用)", "乗用車 (事業用)", "貨物車", "二輪車", "特定小型原付", "自転車", "歩行者", "相手なし・物件",
             "その他・不明"]
    m = np.zeros((len(order), len(order)), dtype=int)
    for r in rows:
        m[order.index(r["party_A"]), order.index(r["party_B"])] = int(r["accidents"])
    keep_a = [i for i in range(len(order)) if m[i].sum() > 0]
    keep_b = [j for j in range(len(order)) if m[:, j].sum() > 0]
    m = m[np.ix_(keep_a, keep_b)]
    fig, ax = plt.subplots(figsize=(8.5, 6))
    im = ax.imshow(m, cmap="YlOrRd", vmin=0)
    ax.set_xticks(range(len(keep_b)), [order[j] for j in keep_b], rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(keep_a)), [order[i] for i in keep_a], fontsize=9)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            if m[i, j]:
                ax.text(j, i, m[i, j], ha="center", va="center", fontsize=8, color="white" if m[i, j] > m.max() * 0.6 else "black")
    ax.set_xlabel("当事者B (過失の軽い側)")
    ax.set_ylabel("当事者A (過失の重い側)")
    fig.colorbar(im, ax=ax, shrink=0.8).set_label("件 (7年合計)")
    ax.set_title(f"港区の人身事故の当事者の組み合わせ (2019〜2025年、n={m.sum():,})", fontsize=11)
    fig.text(0.01, -0.1, "乗用車の事業用はタクシー・ハイヤー・バス等 (用途別が事業用)。当事者Aは被害者かどうかの区分ではない。", fontsize=7)
    save(fig, "party-matrix", "港区の事故は、誰と誰の間で起きているか", ["outputs/party_matrix.csv"], int(m.sum()))


def fig_town_rate(base):
    rows = {r["key_code"]: r for r in read_csv("towns.csv")}
    with (OUT / "town-rate-quantile.json").open(encoding="utf-8") as f:
        meta = json.load(f)
    breaks = meta["breaks"]
    con = duckdb.connect()
    con.sql("load spatial")
    con.sql("set geometry_always_xy = true")
    geoms = con.execute(f"""select KEY_CODE, ST_AsWKB(ST_Transform(ST_GeomFromWKB(geometry), 'EPSG:4612', 'EPSG:6677'))
        from '{(ART / 'towns.parquet').as_posix()}'""").fetchall()
    cmap = ListedColormap(plt.get_cmap("YlOrRd")(np.linspace(0.12, 0.95, len(breaks) - 1)))
    norm = BoundaryNorm(breaks, cmap.N)
    if len(geoms) != len(rows) or len(rows) != 118:
        raise RuntimeError(f"drew {len(geoms)} towns, the analysis has {len(rows)}")
    top = sorted(rows.values(), key=lambda r: -float(r["per_road_km_year"]))[:5]
    fig, ax = plt.subplots(figsize=(9, 9))
    shapes = {}
    for code, g in geoms:
        geom = wkb.loads(g)
        shapes[code] = geom
        v = float(rows[code]["per_road_km_year"])
        for poly in getattr(geom, "geoms", [geom]):
            x, y = poly.exterior.xy
            ax.fill(x, y, color=cmap(norm(v)), ec="#555555", lw=0.3, zorder=0)
    texts = base.draw(ax, road_alpha=0.4)
    for rank, r in enumerate(top, 1):
        geom = shapes[r["key_code"]]
        for poly in getattr(geom, "geoms", [geom]):
            x, y = poly.exterior.xy
            ax.plot(x, y, color="#5b2c83", lw=1.8, zorder=5)
        p = geom.representative_point()
        texts.append(ax.text(p.x, p.y, str(rank), fontsize=9, color="#5b2c83", weight="bold", ha="center",
                             va="center", zorder=8, bbox=NUMBER_BOX))
    handles = [Patch(fc=cmap(i), ec="#555555", label=f"{breaks[i]:.2f}〜{breaks[i + 1]:.2f} ({meta['units_per_class'][i]})")
               for i in range(len(breaks) - 1)]
    handles += [Patch(fc="none", ec="#5b2c83", lw=1.8, label="道路あたりの上位5")]
    handles += [Patch(fc="none", ec="none", label=f"{i}. {r['name']} {float(r['per_road_km_year']):.2f}")
                for i, r in enumerate(top, 1)]
    leg = ax.legend(handles=handles, title="件/道路 km/年 (町丁の数)", loc="upper left", bbox_to_anchor=(1.0, 1.0),
                    fontsize=8, title_fontsize=8)
    overlaps = text_overlaps(fig, texts, [leg])
    ax.set_title("港区のどの町丁で、道路の長さに比べて人身事故が多いか (2019〜2025年)", fontsize=11)
    fig.text(0.01, 0.01, "等分位5階級 (各階級に約24町丁)。道路はOSMの車道の延長で、交通量ではない。" + SOURCE, fontsize=6.5, wrap=True)
    save(fig, "town-rate", "港区のどの町丁で、道路の長さに比べて事故が多いか",
         ["outputs/towns.csv", "outputs/town-rate-quantile.json"], 118,
         f"breaks {breaks};",
         {**CRS_NOTE, "units_drawn": len(geoms), "units_in_analysis": len(rows),
          "highlighted": [r["name"] for r in top], "text_overlaps": overlaps})


def main():
    names = "".join(r["school"] for r in read_csv("schools.csv"))
    names += "".join(h["road_1"] + h["road_2"] for h in read_csv("hotspots.csv"))
    names += "".join(r["party_A"] + r["party_B"] for r in read_csv("party_matrix.csv"))
    use_cjk_font(TEXT + names + SOURCE)
    base = Base()
    fig_trend()
    fig_categories()
    fig_ward_strips()
    fig_hours()
    fig_hour_profile()
    fig_school_map(base)
    fig_hotspots(base)
    fig_hotspot_halves()
    fig_party_matrix()
    fig_town_rate(base)
    print("all figures generated")


if __name__ == "__main__":
    main()
