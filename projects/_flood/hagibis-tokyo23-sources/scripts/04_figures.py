"""Figures from outputs/damage_versions.csv and outputs/evacuation_compare.csv (02_tables.py), each with a JSON of
the same name (question, inputs, n, axes, font).

uvx --with matplotlib python scripts/04_figures.py

- outputs/damage_versions.png: 床上 and 床下 浸水 of 世田谷区 and 大田区 by version of the Tokyo report. Answers: how
  much did the counts move between versions? Points are the reports (棟); the 10-16 report counts 件 and is drawn as
  open points. Lines join only the 棟 points.
- outputs/evacuation_compare.png: per ward, the evacuees in the Tokyo table at 2019-10-13 05:00 and the largest number
  a ward (or MLIT) document gives. Answers: how far is the one table that covers all wards from the peaks? Log axis;
  0 is drawn at the left edge and marked, a blank cell is left out.
"""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "outputs"
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402


def sidecar(png, **kw):
    png.with_suffix(".json").write_text(json.dumps(kw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    with open(OUT / "damage_versions.csv", encoding="utf-8") as f:
        dv = list(csv.DictReader(f))
    with open(OUT / "evacuation_compare.csv", encoding="utf-8") as f:
        ev = list(csv.DictReader(f))

    title = "東京都の被害状況の報の版ごとの床上浸水と床下浸水 (世田谷区と大田区)"
    labels = ["床上浸水", "床下浸水", "世田谷区", "大田区", "報の時点 (2019 年)", "棟 (白抜きは 10-16 の報の文中の件)", "件"]
    src = "出典: 東京都総務局総合防災部「令和元年台風第19号に係る被害状況等について」の各版 (damage_versions.csv)"
    font = use_cjk_font(title + "".join(labels) + src + "0123456789-")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    colours = {"世田谷区": "#d1495b", "大田区": "#2e86ab"}
    for ax, col, name in zip(axes, ("above_floor", "below_floor"), ("床上浸水", "床下浸水")):
        for ward, c in colours.items():
            rows = [r for r in dv if r["ward"] == ward]
            pts = [(dt.datetime.strptime(r["as_of"], "%Y-%m-%d %H:%M"), int(r[col]), r["unit"]) for r in rows]
            tou = [(t, v) for t, v, u in pts if u == "棟"]
            ax.plot([t for t, _ in tou], [v for _, v in tou], "-o", color=c, label=ward, ms=5)
            ken = [(t, v) for t, v, u in pts if u == "件"]
            ax.plot([t for t, _ in ken], [v for _, v in ken], "o", mfc="white", mec=c, ms=7)
        ax.set_title(name, fontsize=10)
        ax.set_xlabel("報の時点 (2019 年)")
        ax.set_ylim(0, None)
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m-%d"))
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("棟 (白抜きは 10-16 の報の文中の件)")
    axes[0].legend(fontsize=9)
    fig.suptitle(title, fontsize=11)
    fig.text(0.01, 0.01, src, fontsize=7)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    png = OUT / "damage_versions.png"
    fig.savefig(png, dpi=130)
    plt.close(fig)
    sidecar(png, question="都の報の版ごとに、世田谷区と大田区の床上・床下浸水の数はどれだけ動いたか",
            inputs=["outputs/damage_versions.csv"], n_points=len(dv), y_axis="棟 (10-16 は件)、0 から",
            note="点は報の版。線は棟の点だけを結ぶ。区間は無い (速報の値そのもの)", font=font)

    title = "避難者の数: 都の表 (2019-10-13 05 時) と、区などの資料の最大の値"
    labels = ["都の表 (13 日 05 時、白抜きは 0 人)", "区などの資料の最大の値", "避難者 (人、対数の軸)", "0 人", "空欄"]
    src = "出典: 都の表は第 1 回 東京都災害対策本部会議の資料、区などの資料は ward_sources.csv の行 (evacuation_compare.csv)"
    wards = [r["ward"] for r in ev]
    font = use_cjk_font(title + "".join(labels) + src + "".join(wards) + "0123456789-,")
    order = sorted(ev, key=lambda r: -(int(r["ward_doc_value"]) if r["ward_doc_value"] else
                                       (int(r["tokyo_20191013_0500"]) if r["tokyo_20191013_0500"] else -1)))
    fig, ax = plt.subplots(figsize=(9, 8))
    zero_x = 5
    for i, r in enumerate(order):
        y = len(order) - 1 - i
        t = r["tokyo_20191013_0500"]
        if t != "":
            v = int(t)
            ax.plot(max(v, zero_x), y, "s", color="#2e86ab", mfc="#2e86ab" if v > 0 else "white", ms=7,
                    label="都の表 (13 日 05 時、白抜きは 0 人)" if i == 0 else None)
        else:
            ax.text(zero_x, y, "空欄", fontsize=7, va="center", ha="left", color="#2e86ab")
        if r["ward_doc_value"]:
            ax.plot(int(r["ward_doc_value"]), y, "o", color="#d1495b", ms=7,
                    label="区などの資料の最大の値" if not any(h.get_label() == "区などの資料の最大の値"
                                                     for h in ax.get_lines()[:-1]) else None)
            if t != "" and int(t) > 0:
                ax.plot([int(t), int(r["ward_doc_value"])], [y, y], color="grey", lw=0.8)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([r["ward"] for r in reversed(order)])
    ax.set_xscale("log")
    ax.set_xlim(zero_x * 0.7, 60000)
    ax.axvline(zero_x, color="grey", lw=0.5, ls=":")
    ax.set_ylim(-0.8, len(order) - 0.4)
    ax.set_xticks([zero_x, 10, 100, 1000, 10000])
    ax.set_xticklabels(["0 人", "10", "100", "1,000", "10,000"])
    ax.set_xlabel("避難者 (人、対数の軸)")
    ax.legend(fontsize=9, loc="lower right")
    ax.set_title(title, fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    fig.text(0.01, 0.01, src, fontsize=6)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    png = OUT / "evacuation_compare.png"
    fig.savefig(png, dpi=130)
    plt.close(fig)
    sidecar(png, question="23 区を全て載せる唯一の表 (都の 13 日 05 時) は、区などの資料の最大の値からどれだけ離れているか",
            inputs=["outputs/evacuation_compare.csv"], n_wards=len(ev),
            n_with_ward_value=sum(1 for r in ev if r["ward_doc_value"]),
            x_axis="人、対数。0 は左端の点線の上に白抜きで描く。都の表の空欄は「空欄」と書く",
            note="区などの資料の値は、最大、総数、ピーク時など資料ごとに意味が違う (evacuation_compare.csv の ward_doc_kind)",
            font=font)
    print("ok")


if __name__ == "__main__":
    main()
