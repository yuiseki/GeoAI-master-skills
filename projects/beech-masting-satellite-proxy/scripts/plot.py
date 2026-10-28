"""Figures of the report, from the outputs of the blocks (no recomputation):
coverage-sites.png, coverage-years.png, within-year-by-model.png, within-year-by-year.png, permutations.png.

From repository root:
    uvx --with matplotlib --with pandas python projects/beech-masting-satellite-proxy/scripts/plot.py \
      projects/beech-masting-satellite-proxy/outputs
"""

import argparse
import json
from pathlib import Path

import pandas as pd

MODELS = ["B0", "R0", "S1", "S2", "RS2"]
LABELS = {"B0": "B0 前年の結実 + ΔT", "R0": "R0 ΔT", "S1": "S1 B0 + 前の夏", "S2": "S2 S1 + 今年の春",
          "RS2": "RS2 ΔT + 衛星 4 つ"}
COLORS = {"B0": "#3b6e8f", "R0": "#8a9bb0", "S1": "#d9a066", "S2": "#c4512a", "RS2": "#7a8f3b"}


def model_rows(b2, b3, scheme):
    """[(model, dev within-year, confirmation within-year)] for one scheme."""
    return [(m, b2[scheme]["scores"][m]["within_year_spearman"], b3["schemes"][scheme]["scores"][m]["within_year_spearman"])
            for m in MODELS]


def site_coverage(cov):
    """Per site: share of target years with a usable acquisition, by window."""
    return cov.assign(ps=cov.prev_summer >= 1, cs=cov.current_spring >= 1).groupby("ID")[["ps", "cs"]].mean()


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs", type=Path)
    o = ap.parse_args().outputs
    load = lambda n: json.loads((o / n).read_text(encoding="utf-8"))  # noqa: E731
    b2, b3, b4 = load("b2_dev_scores.json"), load("b3_confirm.json"), load("b4_falsification.json")
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]

    # 1. sites coloured by spring coverage
    cov = pd.read_csv(o / "coverage_site_year_T1_q79.csv")
    sc = site_coverage(cov)
    sat = pd.read_csv(o / "satellite_seasonal.csv")
    import duckdb

    pos = duckdb.sql("""select ID, Latitude lat, Longitude lon from
        'hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/study_sites.parquet'
        where Location = 'Tohoku region in Honshu'""").df().set_index("ID")
    d = pos.join(sc)
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.2), sharey=True)
    for ax, (col, title) in zip(axes, (("ps", "前の夏 (t − 1 年の 7〜8 月)"), ("cs", "今年の春 (t 年の 4〜5 月)"))):
        s = ax.scatter(d.lon, d.lat, c=d[col], cmap="viridis", vmin=0, vmax=1, s=28, edgecolor="#333333", lw=0.3)
        ax.set_title(title, fontsize=10, loc="left")
        ax.set_xlabel("経度")
        ax.set_aspect(1 / 0.77)
        ax.grid(color="#dddddd", lw=0.5)
    axes[0].set_ylabel("緯度")
    cb = fig.colorbar(s, ax=axes, shrink=0.8, pad=0.02)
    cb.set_label("使える撮影がある年の割合 (目的の年 1990〜2008、T1、有効な画素 79 以上)")
    fig.suptitle("東北 98 地点の Landsat 5 の被覆。春は雪と雲で、半分の年ほどしか使えない", x=0.02, ha="left", fontsize=11)
    fig.savefig(o / "coverage-sites.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 2. rows with all four values by target year
    toh = sat[sat.ID.isin(pos.index)]
    n = toh.dropna(subset=["ndvi_ps", "ndmi_ps", "ndvi_cs", "ndmi_cs"]).groupby("t").size().reindex(range(1990, 2009), fill_value=0)
    rows_c = {int(k): v for k, v in b3["schemes"]["C"]["rows_by_year"].items()}
    fig, ax = plt.subplots(figsize=(10, 3.8))
    ax.bar(n.index, n.values, color=["#9fb3c8" if t <= 1999 else "#e2a27f" for t in n.index], label="4 つの値がそろう地点")
    ax.plot(list(rows_c), list(rows_c.values()), "o", color="#222222", ms=4, label="確認期間の C で採点した行 (評価もある行)")
    ax.axhline(10, color="#c4512a", lw=0.8, ls="--")
    ax.text(1989.6, 11, "10 行 (これ未満の年は年の中の Spearman に入れない)", fontsize=8, color="#c4512a")
    ax.set_xticks(range(1990, 2009, 2))
    ax.set_ylabel("地点の数")
    ax.set_title("目的の年ごとの、衛星の 4 つの値がそろう東北の地点。青は開発期間、橙は確認期間", loc="left", fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(o / "coverage-years.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3. within-year Spearman by model and scheme
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4), sharey=True)
    for ax, s in zip(axes, "ABC"):
        rows = model_rows(b2, b3, s)
        xs = range(len(rows))
        ax.bar([x - 0.2 for x in xs], [r[1] for r in rows], 0.38, color="#cfd8e3", label="開発期間 (探索)")
        ax.bar([x + 0.2 for x in xs], [r[2] for r in rows], 0.38, color=[COLORS[r[0]] for r in rows], label="確認期間")
        for x, r in zip(xs, rows):
            ax.text(x + 0.2, r[2] + 0.01, f"{r[2]:.2f}", ha="center", fontsize=8)
        ax.set_xticks(list(xs), [r[0] for r in rows])
        ax.axhline(0, color="#444444", lw=0.6)
        ax.set_title({"A": "A 未知の年", "B": "B 未知の地点", "C": "C 未知の地点 × 年 (主)"}[s], fontsize=10, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("年の中の Spearman (年を同じ重みで平均)")
    axes[0].legend(fontsize=8, frameon=False, loc="upper right")
    h = b3["gate"]
    fig.suptitle(f"衛星の偏差を足した S1、S2 は、年の中の地点の順位を B0 より下げた (C の S2 − B0 = {h['diff']:+.3f}、"
                 f"90% 区間 {h['lo90']:+.3f}〜{h['hi90']:+.3f})", x=0.02, ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(o / "within-year-by-model.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 4. within-year Spearman by year, scheme C
    by = b3["schemes"]["C"]["within_by_year"]
    fig, ax = plt.subplots(figsize=(10, 4))
    for m in MODELS:
        yrs = list(range(2000, 2009))  # a year without a value breaks the line
        ax.plot(yrs, [by[m].get(str(y), float("nan")) for y in yrs], "-o", ms=4, lw=1.4 if m in ("B0", "S2") else 0.9,
                color=COLORS[m], label=LABELS[m])
    ax.axhline(0, color="#444444", lw=0.6)
    ax.set_xticks(range(2001, 2009))
    ax.set_ylabel("年の中の Spearman (C)")
    ax.set_title("確認期間の年ごとの、年の中の地点の順位相関 (C)。2000 年と 2002 年は行が 10 未満で外れる", loc="left", fontsize=10)
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.1))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(o / "within-year-by-year.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 5. permutations
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    for ax, (k, title) in zip(axes, (("F1_year", "F1 年の並べ替え"), ("F2_site_within_year", "F2 年の中の地点の並べ替え"))):
        f = b4[k]
        ax.hist(f["perm_values"], bins=25, color="#cfd8e3", edgecolor="#9fb3c8")
        ax.axvline(f["real_mean_over_perms"], color="#c4512a", lw=1.6, label=f"実際 {f['real_mean_over_perms']:.3f}")
        ax.axvline(f["perm_p95"], color="#444444", lw=0.8, ls="--", label=f"並べ替えの 95% 点 {f['perm_p95']:.3f}")
        ax.set_title(f"{title}: {'通る' if f['passes'] else '通らない'}", fontsize=10, loc="left")
        ax.set_xlabel("S2 の年の中の Spearman (C、確認期間)")
        ax.legend(fontsize=8, frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("並べ替えの回数 (200 回)")
    fig.tight_layout()
    fig.savefig(o / "permutations.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
