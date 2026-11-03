"""Draw the figures of the 23-ward comparison from outputs/*.csv and outputs/*.json.

Run from the repository root after analyze.py and clusters.py:
env -u PYTHONPATH uvx --with numpy --with matplotlib python projects/_traffic_accident/tokyo23-ward-comparison/scripts/plot.py

Every PNG gets a JSON of the same name: the question, the files read, n, and the font. The maps are drawn by the
skill's classify_map.py (README).
"""

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
OUT = PROJECT / "outputs"
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
sys.dont_write_bytecode = True
from cjk_font import use_cjk_font  # noqa: E402
from context_map import text_overlaps  # noqa: E402

SOURCE = ("出典: 警察庁「交通事故統計情報のオープンデータ」2019-2025年 (yuiseki/npa-traffic-accidents@389500a) を加工。"
          "人口: 国勢調査2020 (jp-admin-2026-09@e6c87b1)。道路: OpenStreetMap 2026-08-31 (osm-tokyo23-src@38f7a5f)")
LABELS = {"share_ped": "歩行者", "share_bike": "自転車", "share_old_ped": "高齢の歩行者",
          "share_young_pb": "若い歩行者・自転車", "share_strict": "生活道路", "share_night": "夜",
          "share_intersection": "交差点", "share_bike_single": "自転車の単独", "share_business_car_A": "事業用の乗用車がA",
          "share_truck_A": "貨物車がA", "share_weekend": "土日", "share_expressway": "首都高速",
          "share_top15_hotspots": "上位15地点", "share_top10pct_towns": "上位10%の町丁"}
GROUP_COLOR = {0: "#c0392b", 1: "#2c7fb8"}
# Ward names on the scatter plots moved from above right of their point (points, x, y), where two would overlap.
PCA_OFFSETS = {"足立区": (-38, -12), "品川区": (-40, 3)}
SCATTER_OFFSETS = {"中野区": (-38, -12), "荒川区": (-42, 3), "文京区": (4, -11), "世田谷区": (4, -11)}


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


def groups():
    """code -> k=2 group, when the k=2 setting passed the rule of C5 (else empty)."""
    rows = read_csv("clusters.csv") if (OUT / "clusters.csv").exists() else []
    return {r["code"]: int(r["group"]) for r in rows if r["k"] == "2"}


def fig_rates(wards):
    keys = [("per_1000_residents_per_year", "人口千人あたり (件/年)"), ("per_road_km_per_year", "道路 1 km あたり (件/年)"),
            ("per_km2_per_year", "面積 1 km² あたり (件/年)")]
    order = sorted(wards, key=lambda w: float(w[keys[0][0]]))
    fig, axes = plt.subplots(1, 3, figsize=(13, 7.5), sharey=True)
    g = groups()
    for ax, (k, label) in zip(axes, keys):
        vals = [float(w[k]) for w in order]
        rank = {w["code"]: i + 1 for i, w in enumerate(sorted(wards, key=lambda w: -float(w[k])))}
        ax.barh(range(len(order)), vals, color=[GROUP_COLOR.get(g.get(w["code"]), "#888888") for w in order])
        for i, (w, v) in enumerate(zip(order, vals)):
            ax.text(v, i, f" {v:g} ({rank[w['code']]})", va="center", fontsize=7)
        ax.set_title(label, fontsize=10)
        ax.set_xlim(0, max(vals) * 1.3)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].set_yticks(range(len(order)), [w["name"] for w in order], fontsize=8)
    fig.suptitle("23区の人身事故の量 (2019〜2025年の年平均)。括弧は23区の中の順位、赤は都心の5区の群", fontsize=11)
    fig.text(0.01, -0.03, "人口は夜間人口 (2020年)。昼の人口と交通量は分母に無く、都心の区の人口あたりは大きく出る。" + SOURCE,
             fontsize=6.5, wrap=True)
    save(fig, "rates", "分母を変えると、区の事故の量の順位はどう変わるか", ["outputs/wards.csv", "outputs/clusters.csv"], 23)


def fig_trend(wards):
    order = sorted(wards, key=lambda w: float(w["ratio_2025_2019"]))
    total = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))["audit"]["ratio_23_wards_2025_2019"]
    color = {"増えた": "#c0392b", "減った": "#2c7fb8", "区別できない": "#9a9a9a"}
    fig, ax = plt.subplots(figsize=(8, 7.5))
    for i, w in enumerate(order):
        ax.plot([1, float(w["ratio_2025_2019"])], [i, i], color="#dddddd", zorder=1)
        ax.scatter([float(w["ratio_2025_2019"])], [i], color=color[w["trend_2025"]], s=40, zorder=2)
        ax.scatter([float(w["ratio_2022_2025_mean_2019"])], [i], marker="|", color="#333333", s=60, zorder=3)
    ax.axvline(1, color="#333333", lw=0.8)
    ax.axvline(total, color="#c0392b", lw=0.8, ls="--")
    ax.text(total, len(order) - 0.3, f" 23区全体 {total:.3f}", color="#c0392b", fontsize=8)
    ax.set_yticks(range(len(order)), [w["name"] for w in order], fontsize=8)
    ax.set_xlabel("2025年の件数 / 2019年の件数 (縦の棒は 2022〜2025年の平均 / 2019年)")
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=f"{k} ({sum(w['trend_2025'] == k for w in wards)}区)")
               for k, c in color.items()]
    ax.legend(handles=handles, loc="lower right", fontsize=8, title="2025年と2019年の95%区間", title_fontsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title("23区の人身事故は2019年から2025年にどう変わったか", fontsize=11)
    fig.text(0.01, -0.03, "区間が重なる区は、増えた、減ったと書かない (区ごとの分析と同じ規則)。" + SOURCE, fontsize=6.5, wrap=True)
    save(fig, "trend", "区ごとに、2019年から2025年に件数はどう変わったか", ["outputs/wards.csv", "outputs/analysis.json"], 23)


def fig_heatmap(wards, z, features):
    g = groups()
    pca = json.loads((OUT / "pca.json").read_text(encoding="utf-8"))
    pc1 = {c: s[0] for c, s in pca["scores"].items()}
    order = sorted(wards, key=lambda w: (g.get(w["code"], 9), -pc1[w["code"]]))
    zs = {r["code"]: r for r in z}
    m = np.array([[float(zs[w["code"]][f]) for f in features] for w in order])
    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(m, cmap="RdBu_r", vmin=-3, vmax=3, aspect="auto")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            share = float(next(w for w in wards if w["code"] == order[i]["code"])[features[j]])
            ax.text(j, i, f"{100 * share:.1f}", ha="center", va="center", fontsize=6.5,
                    color="white" if abs(m[i, j]) >= 2 else "black")
    ax.set_xticks(range(len(features)), [LABELS[f] for f in features], rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(order)), [w["name"] for w in order], fontsize=8)
    if g:
        n0 = sum(1 for w in order if g.get(w["code"]) == 0)
        ax.axhline(n0 - 0.5, color="#333333", lw=1.5)
    fig.colorbar(im, ax=ax, shrink=0.7).set_label("23区の平均からの差 (標準偏差の何倍か)")
    ax.set_title("23区の事故の構成 (数字は区の事故に占める%、色は23区の中での高低)", fontsize=11)
    fig.text(0.01, -0.06, "上の横線より上が都心の5区の群 (k-meansとWard法がともに安定して分けた唯一の分け方)。"
             "群の中は第1主成分の順。" + SOURCE, fontsize=6.5, wrap=True)
    save(fig, "composition", "区の事故の構成は、どこが23区の平均と違うか", ["outputs/features_z.csv", "outputs/wards.csv",
         "outputs/clusters.csv", "outputs/pca.json"], 23)


def fig_pca(wards):
    pca = json.loads((OUT / "pca.json").read_text(encoding="utf-8"))
    g = groups()
    fig, ax = plt.subplots(figsize=(8.5, 7))
    names = []
    for w in wards:
        x, y = pca["scores"][w["code"]][:2]
        ax.scatter([x], [y], color=GROUP_COLOR.get(g.get(w["code"]), "#888888"), s=30)
        names.append(ax.annotate(w["name"], (x, y), xytext=PCA_OFFSETS.get(w["name"], (4, 3)),
                                 textcoords="offset points", fontsize=8))
    ev = pca["explained"]
    ax.axhline(0, color="#cccccc", lw=0.6)
    ax.axvline(0, color="#cccccc", lw=0.6)
    top = lambda i: "、".join(f"{LABELS[f]} {v:+.2f}" for f, v in sorted(pca["loadings"][i].items(),
                                                                    key=lambda kv: -abs(kv[1]))[:4])
    ax.set_xlabel(f"第1主成分 ({100 * ev[0]:.0f}%): {top(0)}", fontsize=8)
    ax.set_ylabel(f"第2主成分 ({100 * ev[1]:.0f}%): {top(1)}", fontsize=8)
    ax.set_title("事故の構成の似た区は近くに並ぶ (12の割合の主成分)", fontsize=11)
    fig.text(0.01, -0.04, "割合は標準化してから主成分にした。赤は都心の5区の群。結果を見た後に足した図 (記録の R005)。" + SOURCE,
             fontsize=6.5, wrap=True)
    save(fig, "composition-pca", "事故の構成で、どの区とどの区が似ているか", ["outputs/pca.json", "outputs/clusters.csv"], 23,
         checks={"text_overlaps": text_overlaps(fig, names)})


def fig_concentration(wards):
    fig, ax = plt.subplots(figsize=(7.5, 6))
    g = groups()
    names = []
    for w in wards:
        x, y = 100 * float(w["share_top15_hotspots"]), 100 * float(w["share_top10pct_towns"])
        ax.scatter([x], [y], color=GROUP_COLOR.get(g.get(w["code"]), "#888888"), s=30)
        names.append(ax.annotate(w["name"], (x, y), xytext=SCATTER_OFFSETS.get(w["name"], (4, 3)),
                                 textcoords="offset points", fontsize=8))
    ax.set_xlabel("区の事故のうち、30 m の地点の上位15に入る割合 (%)")
    ax.set_ylabel("区の事故のうち、件数の上位10%の町丁に入る割合 (%)")
    ax.set_title("区の事故はどれだけ少数の場所に集まっているか", fontsize=11)
    fig.text(0.01, -0.04, "町丁は国勢調査の小地域を KEY_CODE でまとめた単位 (水面を除く)。町丁の数は区で違う (52〜277)。" + SOURCE,
             fontsize=6.5, wrap=True)
    save(fig, "concentration", "区の事故は、少数の地点や町丁に集まっているか", ["outputs/wards.csv"], 23,
         checks={"text_overlaps": text_overlaps(fig, names)})


def main():
    wards = read_csv("wards.csv")
    z = read_csv("features_z.csv")
    features = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))["settings"]["features"]
    use_cjk_font("".join(w["name"] for w in wards) + "".join(LABELS.values()) + SOURCE
                 + "0123456789.,%()/〜²年件人口千あたり道路面積順位括弧赤都心区群平均差標準偏差何倍数字構成色高低上横線分け方"
                 "唯一主成分第割合似近並結果見後足図記録縦棒全体増減区別できない間重書規則同じ量夜間昼交通分母大きく出"
                 "地点町丁国勢調査小地域単位水面除少数集まいるかどれだけ変わ")
    fig_rates(wards)
    fig_trend(wards)
    fig_heatmap(wards, z, features)
    fig_pca(wards)
    fig_concentration(wards)


if __name__ == "__main__":
    main()
