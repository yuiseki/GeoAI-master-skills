"""Draw the figures of the Shinjuku accident reports from outputs/*.csv and the artifacts.

Run from the repository root after analyze.py:
uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib \
  python projects/_traffic_accident/shinjuku-accident-trends-by-role/scripts/plot.py

Maps are drawn in EPSG:6677 (JGD2011 plane IX, metres) so that 500 m and 30 m circles are round.
Every PNG gets a JSON of the same name: the question, the files read, n, versions, and the font.
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.patches import Circle, Patch, Rectangle  # noqa: E402
from shapely import wkb  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
ART = ROOT / "artifacts/_traffic_accident/shinjuku-accident-trends-by-role"
OUT = PROJECT / "outputs"
# The ward: code5 in wards.parquet and its name in the titles (市区町村コード 104 in the honhyo).
WARD5 = "13104"
WARD_NAME = "新宿区"
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402
from context_map import text_overlaps  # noqa: E402

# Roads are OGC:CRS84 and the ward and towns JGD2000 (EPSG:4612); both are reprojected to EPSG:6677 as if
# the datums were the same. The difference (about 1 m, per map-context) is under a road line's width here.
CRS_NOTE = {"map_crs": "EPSG:6677", "background": "roads OGC:CRS84, ward and towns EPSG:4612",
            "accepted_difference": "JGD2000 と WGS84 の差 (約 1 m) は道路の線の幅より小さい"}
NUMBER_BOX = dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9)

SOURCE = ("出典: 警察庁「交通事故統計情報のオープンデータ」2019-2025年 (yuiseki/npa-traffic-accidents@389500a) を加工。"
          "背景: OpenStreetMap 2026-08-31 (osm-tokyo23-src@38f7a5f)、国勢調査2020小地域 (estat-boundary-2020@823195c)")
# Place names drawn on the maps: label -> the census town (S_NAME) whose inner point carries it. Chosen from
# Shinjuku's towns so that the parts of the ward can be named; S_NAME values that appear twice (四谷, 山吹町)
# are not used, since Base.towns keeps one shape per name. 神楽坂 is written on 神楽坂六丁目: on 神楽坂三丁目 (first
# draw) it covered the hatched town without a road (神楽坂四丁目) and touched number 2 (神楽河岸) on town-rate.png.
LANDMARKS = {"西新宿": "西新宿二丁目", "歌舞伎町": "歌舞伎町一丁目", "新宿御苑": "内藤町", "四谷": "四谷二丁目",
             "市谷": "市谷本村町", "神楽坂": "神楽坂六丁目", "早稲田": "早稲田鶴巻町", "高田馬場": "高田馬場二丁目",
             "大久保": "大久保二丁目", "落合": "中落合二丁目", "戸山": "戸山一丁目", "北新宿": "北新宿二丁目"}
# The zoom of the hotspot map: the hotspots around Shinjuku station's east and north side (新宿三〜七丁目,
# 歌舞伎町, 西新宿七丁目), chosen after the first run of analyze.py, EPSG:6677 metres (xmin, xmax, ymin, ymax).
ZOOM_BOX = (-12400, -11200, -34600, -33300)
ZOOM_NAME = "新宿駅の東と北 (新宿三〜七丁目・歌舞伎町)"
# (panel, rank) -> (dx, dy) in metres for hotspot numbers that need to move; panel 0 is the ward, 1 the zoom.
# Rank 14 sits under the name 高田馬場 when written above right (first draw, 2026-11-03); write it below right.
NUDGE = {(0, "14"): (80, -170)}
# The town numbers on town-rate.png: rank -> (dx, dy) in metres from the town's inner point, for the ones that
# overlap; and the landmark names left out there because a numbered town sits under them.
TOWN_NUDGE = {}
TOWN_SKIP = ()
MAJOR = {"motorway", "trunk", "primary", "secondary", "trunk_link", "primary_link"}
WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"]
TEXT = ("0123456789,.%()/-−×・:年月日時件人数率区新宿23全自転車歩行者高齢若い生活道路狭広交差点夜電動キックボード特定小型原付"
        "住民千あたり曜の数学校と半径内外中心新宿西歌舞伎町御苑四谷市神楽坂早稲田高馬場大久保落合戸山北凡例出典警察庁交通事故統計情報オープンデータを加工背景"
        "地図地点前半後半当事者AB乗用事業家用貨物二輪相手なし物件その他不明北方向〜以上未満町丁ごとの道路あたり読みの指数基準百分位階級"
        "等間隔分割種類過失重い側主若者件区間95%Poissonの範囲順位立場選ぶ半分割合色点円上位1530m500mkmyNEnsitivityxv"
        "数えた本票ファイル計上されたと関わる以内線括弧単路信号小中高大集まり平均昼間別回目下位帯を描く都心側ここ灰色黒白赤青黄緑紫"
        "通り首都高速明治靖国新宿甲州街道外苑東小滝橋角筈和泉町線山手文化センター職安区役所花道新目白外堀コズミック御苑早稲田"
        "比べる位置向きスケールバーOSMの道路のうち幹線を太く7年合計ありWeekday土日平日無い値NoData東と三七丁目駅")


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
        self.ward = wkb.loads(con.execute(f"select {tr.format('EPSG:4612')} from '{ART / 'wards.parquet'}' "
                                          f"where code5 = '{WARD5}'").fetchall()[0][0])
        self.roads = [(h, wkb.loads(g)) for h, g in con.execute(
            f"select highway, {tr.format('OGC:CRS84')} from '{ART / 'roads.parquet'}'").fetchall()]
        self.towns = {n: (wkb.loads(g), wkb.loads(g2)) for n, g, g2 in con.execute(
            f"select S_NAME, {tr.format('EPSG:4612')}, ST_AsWKB(ST_GeomFromWKB(geometry)) from '{ART / 'towns.parquet'}'").fetchall()}
        with (ART / "points.csv").open(encoding="utf-8") as f:
            self.points = [{k: (v == "True" if v in ("True", "False") else float(v) if k in ("x", "y") else int(v)
                                if k in ("weekday", "hour") else v) for k, v in r.items()} for r in csv.DictReader(f)]
        self.schools = con.execute(f"""select name,
            ST_X(ST_Transform(ST_Point(lon, lat), 'OGC:CRS84', 'EPSG:6677')),
            ST_Y(ST_Transform(ST_Point(lon, lat), 'OGC:CRS84', 'EPSG:6677')) from '{ART / 'schools.parquet'}'""").fetchall()

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
            pad = 150
            extent = (xmin - pad, xmax + pad, ymin - pad, ymax + pad)
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        texts = []
        if labels:
            for label, town in LANDMARKS.items():
                if label in skip:
                    continue
                p = self.towns[town][0].representative_point()
                if extent[0] < p.x < extent[1] and extent[2] < p.y < extent[3]:
                    texts.append(ax.text(p.x, p.y, label, fontsize=8, color="#222222", ha="center", va="center",
                                         zorder=6, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7)))
        self.scalebar(ax, extent)
        return texts

    @staticmethod
    def scalebar(ax, extent, length=500):
        x0 = extent[0] + 0.05 * (extent[1] - extent[0])
        y0 = extent[2] + 0.04 * (extent[3] - extent[2])
        length = 500 if extent[1] - extent[0] > 2000 else 100
        ax.add_patch(Rectangle((x0, y0), length, 0.006 * (extent[3] - extent[2]), color="black", zorder=7))
        ax.text(x0 + length / 2, y0 + 0.015 * (extent[3] - extent[2]), f"{length} m", ha="center", fontsize=8, zorder=7)
        ax.text(extent[1] - 0.04 * (extent[1] - extent[0]), extent[3] - 0.05 * (extent[3] - extent[2]), "北↑",
                ha="right", fontsize=9, zorder=7)


def fig_trend():
    rows = read_csv("yearly.csv")
    fig, ax = plt.subplots(figsize=(7, 4))
    top = 0.0
    for scope, color in ((WARD_NAME, "#c0392b"), ("23区", "#555555")):
        rs = [r for r in rows if r["scope"] == scope]
        years = [int(r["year"]) for r in rs]
        base = float(rs[0]["accidents"])
        idx = [float(r["index_2019"]) for r in rs]
        lo = [100 * float(r["lo95"]) / base for r in rs]
        hi = [100 * float(r["hi95"]) / base for r in rs]
        top = max(top, *hi)
        ax.fill_between(years, lo, hi, color=color, alpha=0.15, lw=0)
        ax.plot(years, idx, marker="o", color=color, label=f"{scope} (2019年 {int(base):,}件)")
    ax.axhline(100, color="#999999", lw=0.8, ls=":")
    # Taito fixed 60 to 115; Shinjuku's index reaches 161.5 (2025), so the top follows the highest interval.
    ax.set_ylim(60, max(115, 5 * np.ceil(top / 5) + 5))
    ax.set_xlabel("年 (統計に計上された年)")
    ax.set_ylabel("人身事故件数の指数 (2019年=100)")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title(f"{WARD_NAME}と23区の人身事故件数の推移", fontsize=11)
    ax.text(0, -0.2, "帯: 各年の件数のPoisson 95%区間を指数に換算。" + SOURCE[:40] + "…", transform=ax.transAxes, fontsize=7)
    save(fig, "trend-index", f"{WARD_NAME}の事故件数は23区全体と比べてどう推移したか", ["outputs/yearly.csv"],
         {r["scope"]: sum(int(x["accidents"]) for x in rows if x["scope"] == r["scope"]) for r in rows},
         "縦軸は60から始まる (指数の比較のため)。帯は年ごとの件数の記録の揺れの目安で、年をまたぐ差の検定ではない")


def fig_categories():
    rows = [r for r in read_csv("yearly.csv") if r["scope"] == WARD_NAME]
    years = [int(r["year"]) for r in rows]
    panels = [("bike", "自転車が関わる"), ("ped", "歩行者が関わる"), ("old_ped", "高齢 (65歳以上) の歩行者が関わる"),
              ("young_pb", "若い (0〜24歳) 歩行者・自転車が関わる"), ("strict", "生活道路 (狭い読み / 広い読み)"),
              ("escooter", "特定小型原付 (電動キックボード等) が関わる")]
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.6), sharex=True)
    for ax, (key, title) in zip(axes.flat, panels):
        ax.plot(years, [int(r[key]) for r in rows], marker="o", color="#c0392b", label="狭い読み" if key == "strict" else None)
        if key == "strict":
            ax.plot(years, [int(r["broad"]) for r in rows], marker="s", color="#2c7fb8", label="広い読み")
            ax.legend(fontsize=8, loc="lower left")
        ax.set_ylim(0, None)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("件", fontsize=9)
        ax.grid(axis="y", color="#eeeeee")
    fig.suptitle(f"{WARD_NAME}の人身事故のうち、当事者や道路の種類ごとの件数 (年)", fontsize=11)
    fig.text(0.01, -0.01, "当事者AかBのどちらかが当てはまる事故を1件と数える。特定小型原付は2024年からの区分。" + SOURCE[:46] + "…",
             fontsize=7)
    fig.tight_layout()
    save(fig, "shinjuku-categories", f"{WARD_NAME}で、どの種類の事故が年ごとにどう動いたか", ["outputs/yearly.csv"],
         sum(int(r["accidents"]) for r in rows), "縦軸は全て0から。パネルごとに縦軸の範囲が違う")


def fig_ward_strips():
    rows = read_csv("wards.csv")
    metrics = [("share_bike", "自転車が関わる割合 (%)", 100), ("share_ped", "歩行者が関わる割合 (%)", 100),
               ("share_old_ped", "高齢歩行者が関わる割合 (%)", 100), ("share_young_pb", "若い歩行者・自転車の割合 (%)", 100),
               ("share_strict", "生活道路 (狭い読み) の割合 (%)", 100), ("share_intersection", "交差点内の割合 (%)", 100),
               ("share_night", "夜の割合 (%)", 100), ("per_1000_residents_per_year", "住民千人あたり件数/年 (参考)", 1)]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(8, 7.2))
    for ax, (key, label, k) in zip(axes, metrics):
        vals = [(float(r[key]) * k, r["name"]) for r in rows]
        xs = [v for v, _ in vals]
        ax.scatter([v for v, n in vals if n != WARD_NAME], [0] * 22, color="#9a9a9a", s=22, zorder=2)
        own = next(v for v, n in vals if n == WARD_NAME)
        ax.scatter([own], [0], color="#c0392b", s=60, zorder=3)
        rank = 1 + sum(v > own for v in xs)
        ax.text(own, 0.45, f"{WARD_NAME} {own:.1f} ({rank}位/23)", color="#c0392b", fontsize=8, ha="center")
        for v, n in vals:
            if v in (max(xs), min(xs)) and n != WARD_NAME:
                ax.text(v, -0.6, n, fontsize=7, ha="center", color="#555555")
        ax.set_yticks([])
        ax.set_ylim(-1, 1)
        ax.set_title(label, fontsize=9, loc="left", pad=2)
        for side in ("left", "right", "top"):
            ax.spines[side].set_visible(False)
        lo, hi = min(xs), max(xs)
        ax.set_xlim(lo - 0.08 * (hi - lo), hi + 0.08 * (hi - lo))
    fig.suptitle(f"23区の中の{WARD_NAME} (2019〜2025年の7年合計の構成)", fontsize=11)
    fig.text(0.01, -0.01, "灰色の点がほかの22区。順位は値の大きい順。住民千人あたりは2020年国勢調査の夜間人口で割った参考値で、"
             "昼の人口と交通量を含まない。", fontsize=7)
    fig.tight_layout()
    save(fig, "ward-strips", f"{WARD_NAME}の事故の構成は、23区の中でどこにあるか", ["outputs/wards.csv"],
         sum(int(r["accidents"]) for r in rows), "各行で横軸の範囲は違う。0から始まらない (割合の位置を比べる図)")


def fig_hours():
    rows = read_csv("hour_weekday.csv")
    groups = [("全て", "全ての人身事故"), ("若い歩行者・自転車", "若い (0〜24歳) 歩行者・自転車が関わる事故")]
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
        cb.set_label("件 (7年合計)", fontsize=8)
        ns[g] = int(m.sum())
    fig.suptitle(f"{WARD_NAME}の人身事故の曜日と時刻 (2019〜2025年)", fontsize=11)
    fig.text(0.01, -0.03, "パネルごとに色の範囲が違う。時刻は発生した時 (0時台〜23時台)。" + SOURCE[:46] + "…", fontsize=7)
    fig.tight_layout()
    save(fig, "hour-weekday", f"{WARD_NAME}の事故は何曜日の何時に多いか。若い歩行者と自転車では違うか",
         ["outputs/hour_weekday.csv"], ns, "色の範囲はパネルごと")


def fig_hour_profile():
    rows = read_csv("hour_weekday.csv")
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for g, color in (("自転車", "#2c7fb8"), ("全て", "#555555"), ("高齢の歩行者", "#c0392b")):
        c = defaultdict(int)
        for r in rows:
            if r["group"] == g:
                c[int(r["hour"])] += int(r["accidents"])
        ax.plot(range(24), [c[h] for h in range(24)], marker="o", ms=3, color=color, label=f"{g} (n={sum(c.values()):,})")
    ax.set_xticks(range(0, 24, 3), [f"{h}時" for h in range(0, 24, 3)])
    ax.set_ylim(0, None)
    ax.set_ylabel("件 (7年合計)")
    ax.set_xlabel("発生した時刻")
    ax.legend(fontsize=9)
    ax.grid(axis="y", color="#eeeeee")
    ax.set_title(f"{WARD_NAME}の人身事故の時刻 (2019〜2025年、全ての曜日)", fontsize=11)
    save(fig, "hour-profile", "一日のどの時間に、どんな人が関わる事故が多いか", ["outputs/hour_weekday.csv"], None,
         "高齢の歩行者は件数が少なく、同じ縦軸では低く見える")


def fig_school_map(base):
    pts = [p for p in base.point_rows() if p["young_pb"]]
    schools = read_csv("schools.csv")
    fig, ax = plt.subplots(figsize=(8, 8))
    texts = base.draw(ax)
    xy = {n: (x, y) for n, x, y in base.schools}
    for s in schools:
        x, y = xy[s["school"]]
        ax.add_patch(Circle((x, y), 500, fill=False, ec="#2c7fb8", lw=0.6, alpha=0.6, zorder=3))
        ax.plot(x, y, marker="s", color="#2c7fb8", ms=5, zorder=5)
    weekday_peak = [p for p in pts if 2 <= p["weekday"] <= 6 and (7 <= p["hour"] <= 8 or 14 <= p["hour"] <= 17)]
    other = [p for p in pts if p not in weekday_peak]
    ax.scatter([p["x"] for p in other], [p["y"] for p in other], s=7, color="#f39c12", alpha=0.7, zorder=4,
               label=f"その他の時間 ({len(other)}件)")
    ax.scatter([p["x"] for p in weekday_peak], [p["y"] for p in weekday_peak], s=12, color="#c0392b", zorder=4,
               label=f"平日 7〜8時台・14〜17時台 ({len(weekday_peak)}件)")
    ax.legend(handles=[ax.collections[0], ax.collections[1],
                       plt.Line2D([], [], marker="s", color="#2c7fb8", ls="", label=f"小学校・中学校 ({len(schools)}校、OSM)"),
                       Patch(fc="none", ec="#2c7fb8", label="学校から半径 500 m")], loc="upper left",
              bbox_to_anchor=(1.0, 1.0), fontsize=8)
    overlaps = text_overlaps(fig, texts, [ax.get_legend()])
    ax.set_title(f"若い (0〜24歳) 歩行者・自転車が関わる人身事故と学校 ({WARD_NAME}、2019〜2025年)", fontsize=10)
    fig.text(0.01, 0.01, SOURCE, fontsize=6, wrap=True)
    save(fig, "school-map", "学校の周りで、若い歩行者と自転車の事故はどこで起きているか",
         ["artifacts/_traffic_accident/shinjuku-accident-trends-by-role/points.csv", "outputs/schools.csv"],
         {"young_ped_or_bike": len(pts), "weekday_7_8_or_14_17": len(weekday_peak)},
         "0〜24歳は年齢層の最小の区分で、小学生だけを示すものではない。円は直線距離",
         {**CRS_NOTE, "schools_drawn": len(schools), "text_overlaps": overlaps})


def fig_hotspots(base):
    hot = read_csv("hotspots.csv")
    pts = base.point_rows()
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.2), gridspec_kw={"width_ratios": [1, 1]})
    xs = [float(h["x"]) for h in hot[:15]]
    ys = [float(h["y"]) for h in hot[:15]]
    # The zoom covers the hotspots around Shinjuku station's east and north side only (ZOOM_BOX).
    uz = [(x, y) for x, y in zip(xs, ys) if ZOOM_BOX[0] < x < ZOOM_BOX[1] and ZOOM_BOX[2] < y < ZOOM_BOX[3]]
    zoom = (min(x for x, _ in uz) - 200, max(x for x, _ in uz) + 200,
            min(y for _, y in uz) - 200, max(y for _, y in uz) + 200)
    texts = {0: [], 1: []}
    top_n = max(int(h["accidents"]) for h in hot)
    zoomed = []
    for i, ax in enumerate(axes):
        if i == 0:
            texts[0] += base.draw(ax)
        else:
            base.draw(ax, extent=zoom, labels=False)
        ax.scatter([p["x"] for p in pts], [p["y"] for p in pts], s=2 if i == 0 else 5, color="#555555", alpha=0.35,
                   zorder=3, lw=0)
        for h in hot:
            x, y, n = float(h["x"]), float(h["y"]), int(h["accidents"])
            inside = zoom[0] < x < zoom[1] and zoom[2] < y < zoom[3]
            if inside or i == 0:
                # Taito used 0.35 + 0.015 n, which passes 1 above 43 accidents (Shinjuku's top has 47); the
                # opacity now runs from 0.35 to 0.95 at the largest count, still linear in n.
                ax.add_patch(Circle((x, y), 30, fc="#c0392b", ec="#7b241c", alpha=0.35 + 0.6 * n / top_n, zorder=4))
            if (i == 1 and inside) or (i == 0 and not inside):
                # Offsets of the number from the circle, in metres (above right by default). NUDGE moves the
                # numbers that overlap a place name or another number; see the text_overlaps of the first draw.
                dx, dy = NUDGE.get((i, h["rank"]), (45, 25) if i else (70, 50))
                texts[i].append(ax.text(x + dx, y + dy, h["rank"],
                                        fontsize=8 if i == 0 else 10, color="#7b241c", weight="bold", zorder=6,
                                        bbox=NUMBER_BOX))
            elif i == 0:
                zoomed.append(int(h["rank"]))
        if i == 0:
            ax.add_patch(Rectangle((zoom[0], zoom[2]), zoom[1] - zoom[0], zoom[3] - zoom[2], fill=False, ec="#2c7fb8",
                                   lw=1.2, ls="--", zorder=6))
    axes[0].set_title(f"{WARD_NAME}の人身事故 {len(pts):,}件 (灰色の点) と、事故の多い地点の上位15 (赤い円、半径30 m)", fontsize=10)
    axes[1].set_title(f"{ZOOM_NAME}の拡大 (左の青い枠。枠の中の番号はこちらに書いた)", fontsize=10)
    fig.text(0.01, 0.01, "地点は、半径30 mの円の中の7年の事故数が多い順に、重ならないように選んだ。番号は順位。" + SOURCE,
             fontsize=7, wrap=True)
    overlaps = text_overlaps(fig, texts[0]) + text_overlaps(fig, texts[1])
    save(fig, "hotspots-map", f"{WARD_NAME}で人身事故が集まる地点はどこか",
         ["artifacts/_traffic_accident/shinjuku-accident-trends-by-role/points.csv", "outputs/hotspots.csv"], len(pts),
         "位置の精度は不明。円の濃さは件数に比例",
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
    ax.set_title("事故の多い地点の上位15: 前半と後半の年平均", fontsize=11)
    fig.text(0.01, -0.02, "地点名は、地点の中心に最も近いOSMの道路名 (2本目は30 m以内のときだけ)。首都高速の名前は除いた。", fontsize=7)
    save(fig, "hotspot-halves", "事故の多い地点は、前半と後半で続いているか", ["outputs/hotspots.csv"],
         sum(int(h["accidents"]) for h in hot), "上位は7年合計で選んだので、選んだ期間と同じデータで見ている (平均への回帰が起きうる)")


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
    ax.set_title(f"{WARD_NAME}の人身事故の当事者の組み合わせ (2019〜2025年、n={m.sum():,})", fontsize=11)
    fig.text(0.01, -0.1, "乗用車の事業用はタクシー・ハイヤー・バス等 (用途別が事業用)。当事者Aは被害者かどうかの区分ではない。", fontsize=7)
    save(fig, "party-matrix", f"{WARD_NAME}の事故は、誰と誰の間で起きているか", ["outputs/party_matrix.csv"], int(m.sum()))


def fig_town_rate(base):
    rows = {r["key_code"]: r for r in read_csv("towns.csv")}
    meta = json.loads((OUT / "town-rate-quantile.json").read_text(encoding="utf-8"))
    audit = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))["audit"]
    # The share of towns changing class, quantile vs equal: printed by classify_map.py (README), kept in tmp/.
    log = (PROJECT / "tmp/classify_map.log").read_text(encoding="utf-8")
    changed = float(log.split("units changing class, quantile vs equal: ")[1].split()[0])
    breaks = [float(b) for b in meta["breaks"]]
    con = duckdb.connect()
    con.sql("load spatial")
    con.sql("set geometry_always_xy = true")
    # The analysed units (one per KEY_CODE, pieces merged by analyze.py), not the rows of towns.parquet.
    geoms = con.execute(f"""select KEY_CODE, ST_AsWKB(ST_Transform(geometry, 'EPSG:4612', 'EPSG:6677'))
        from '{ART / 'town_counts.parquet'}'""").fetchall()
    cmap = ListedColormap(plt.get_cmap("YlOrRd")(np.linspace(0.12, 0.95, len(breaks) - 1)))
    norm = BoundaryNorm(breaks, cmap.N)
    if len(geoms) != len(rows) or len(rows) != audit["towns"]:
        raise RuntimeError(f"drew {len(geoms)} towns, towns.csv has {len(rows)}, the analysis {audit['towns']}")
    # Towns with no road have no rate (NoData, an empty cell in towns.csv); they are drawn grey and hatched.
    nodata = [r for r in rows.values() if r["per_road_km_year"] == ""]
    if len(nodata) != meta["nodata_units"] or len(nodata) != len(audit["towns_without_road"]):
        raise RuntimeError(f"{len(nodata)} towns without a value; classify_map.py had {meta['nodata_units']}")
    top = sorted((r for r in rows.values() if r not in nodata), key=lambda r: -float(r["per_road_km_year"]))[:5]
    fig, ax = plt.subplots(figsize=(8.5, 8))
    shapes = {}
    for code, g in geoms:
        geom = wkb.loads(g)
        shapes[code] = geom
        v = rows[code]["per_road_km_year"]
        for poly in getattr(geom, "geoms", [geom]):
            x, y = poly.exterior.xy
            if v == "":
                ax.fill(x, y, fc="#dddddd", ec="#555555", lw=0.4, hatch="////", zorder=0)
            else:
                ax.fill(x, y, color=cmap(norm(float(v))), ec="#555555", lw=0.4, zorder=0)
    texts = base.draw(ax, road_alpha=0.5, skip=TOWN_SKIP)
    # The top five towns: outlined, numbered on white, named in the legend (map-context 7 and 12).
    for rank, r in enumerate(top, 1):
        geom = shapes[r["key_code"]]
        for poly in getattr(geom, "geoms", [geom]):
            x, y = poly.exterior.xy
            ax.plot(x, y, color="#5b2c83", lw=1.8, zorder=5)
        p = geom.representative_point()
        dx, dy = TOWN_NUDGE.get(rank, (0, 0))
        texts.append(ax.text(p.x + dx, p.y + dy, str(rank), fontsize=9, color="#5b2c83", weight="bold", ha="center",
                             va="center", zorder=8, bbox=NUMBER_BOX))
    handles = [Patch(fc=cmap(i), ec="#555555", label=f"{breaks[i]:.2f}〜{breaks[i + 1]:.2f} ({meta['units_per_class'][i]})")
               for i in range(len(breaks) - 1)]
    handles += [Patch(fc="#dddddd", ec="#555555", hatch="////", label=f"道路の無い町丁 (値なし) ({len(nodata)})")]
    handles += [Patch(fc="none", ec="#5b2c83", lw=1.8, label="道路あたりの上位5")]
    handles += [Patch(fc="none", ec="none", label=f"{i}. {r['name']} {float(r['per_road_km_year']):.2f}")
                for i, r in enumerate(top, 1)]
    leg = ax.legend(handles=handles, title="件/道路 km/年 (町丁の数)", loc="upper left", bbox_to_anchor=(1.0, 1.0),
                    fontsize=8, title_fontsize=8)
    overlaps = text_overlaps(fig, texts, [leg])
    ax.set_title(f"{WARD_NAME}のどの町丁で、道路の長さに比べて人身事故が多いか (2019〜2025年)", fontsize=11)
    per_class = round((len(rows) - len(nodata)) / (len(breaks) - 1))
    fig.text(0.01, 0.01, f"分位5階級 (各階級に約{per_class}町丁)。等間隔5階級にすると{100 * changed:.0f}%の町丁の色が変わる。"
             "道路はOSMの車道の延長で、交通量ではない。"
             f"町丁の外の{audit['points_outside_towns']}件は入らない。"
             f"斜線は町丁の中にOSMの車道が無く値の無い町丁 ({'、'.join(t['name'] for t in audit['towns_without_road'])})。"
             + SOURCE, fontsize=6.5, wrap=True)
    save(fig, "town-rate", f"{WARD_NAME}のどの町丁で、道路の長さに比べて事故が多いか",
         ["outputs/towns.csv", "outputs/town-rate-quantile.json", "outputs/analysis.json"], len(geoms),
         f"breaks {breaks}; 分位と等間隔で色の変わる町丁 {changed} (classify_map.py の出力); "
         f"値の無い町丁 {len(nodata)} ({'、'.join(r['name'] for r in nodata)})",
         {**CRS_NOTE, "units_drawn": len(geoms), "units_in_analysis": len(rows),
          "highlighted": [r["name"] for r in top], "text_overlaps": overlaps})


def main():
    names = "".join(r["school"] for r in read_csv("schools.csv"))
    names += "".join(h["road_1"] + h["road_2"] for h in read_csv("hotspots.csv"))
    names += "".join(r["party_A"] + r["party_B"] for r in read_csv("party_matrix.csv"))
    names += "".join(LANDMARKS) + ZOOM_NAME + "".join(r["name"] for r in read_csv("towns.csv"))
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


if __name__ == "__main__":
    main()
