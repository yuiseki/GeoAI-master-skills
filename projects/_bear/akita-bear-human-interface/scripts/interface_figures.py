"""The report's figures, drawn from the saved outputs (JSON) and score files; nothing is refitted.

    capture-by-role.png    capture@5% of the role subsets in B1-B3, and the main differences with 90% intervals
    phase-space.png        positive-cell share and rate lift in the 25 equal-quintile bins, 2023-2026
    phase-space-top.png    the same with the post-hoc bins cut at 0.50/0.80/0.90/0.95 (exploratory)
    year-shift.png         where the April-September positives of 2025 and 2026 sit on the B2 axes, and the level/lean
                           Cliff's deltas of the adjacent pairs
    falsification.png      F1 (real split among 20 random ones) and F2 (block shuffle) against the observed values
    reporting.png          Akita City share, reports per positive cell, sighting share and top human-side quintile
    map-phase-classes.png  the prefecture coloured by the B2 axes (both, bear-side only, human-side only in the top 10%)
                           with the 2025 and 2026 positives

From repository root:
    PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
      env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
      uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy --with pandas --with pyarrow --with shapely \
      --with matplotlib --with pyproj python projects/_bear/akita-bear-human-interface/scripts/interface_figures.py \
      artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-human-interface \
      projects/_bear/akita-bear-human-interface/outputs
"""

import argparse
import json
from pathlib import Path

import numpy as np

import phase as ph

SPLITS = [("b1_dev_2023_to_2024.json", "B1: 2023 → 2024 (開発)", "#b9c4d0"),
          ("b2_confirm_2023-2024_to_2025.json", "B2: 2023+2024 → 2025 (確認)", "#7a8fa6"),
          ("b3_confirm_2023-2025_to_2026.json", "B3: 2023〜2025 → 2026 年 4〜9 月 (確認)", "#1f4e79")]
MODELS = [("M_B", "M_B (bear-side、10)"), ("M_H", "M_H (human-side、12)"), ("M_I", "M_I (interface、1)"),
          ("M_BH", "M_BH (B + H、22)"), ("M_BHI", "M_BHI (B + H + I、23)"), ("M_FULL", "M_FULL = B_env (28)")]
DIFFS = [("M_B - M_H", "M_B − M_H"), ("M_BH - M_H", "M_BH − M_H"), ("M_BHI - M_BH", "M_BHI − M_BH"),
         ("M_FULL - M_BHI", "M_FULL − M_BHI")]
SOURCE = ("通報 akita-kumadas c7047ab (2026-09-30)。100 m のセル (EPSG:6678)。特徴量 ESA WorldCover 2021、GSI 標高、"
          "WorldPop 2020、OSM 2026-08")
C_B, C_H, C_BOTH = "#2e7d4f", "#b5651d", "#5b2a86"


def j(out, name):
    return json.load(open(Path(out) / name, encoding="utf-8"))


def capture_by_role(out, plt):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw={"width_ratios": [1.25, 1]})
    for k, (f, lab, col) in enumerate(SPLITS):
        d = j(out, f)
        ys = np.arange(len(MODELS))[::-1] + (k - 1) * 0.22
        a1.scatter([d[m]["capture@5%"] for m, _ in MODELS], ys, color=col, s=34, label=lab, zorder=3)
        if k:
            yd = np.arange(len(DIFFS))[::-1] + (k - 1.5) * 0.3
            for y, (key, _) in zip(yd, DIFFS):
                v = d["diff_capture@5%"][key]
                a2.plot([v["lo90"], v["hi90"]], [y, y], color=col, lw=2.2)
                a2.plot(v["diff"], y, "o", color=col, ms=5)
    a1.axvline(0.05, color="#999999", lw=0.8, ls=":")
    a1.text(0.055, len(MODELS) - 0.6, "無作為 0.05", fontsize=8, color="#777777")
    a1.set_yticks(range(len(MODELS)))
    a1.set_yticklabels([lab for _, lab in MODELS][::-1], fontsize=9)
    a1.set_xlabel("capture@5% (上位 5% のセルに入った、通報のあったセルの割合)")
    a1.set_xlim(0, 0.62)
    a1.legend(fontsize=8, loc="lower right", frameon=False)
    a1.set_title("human-side だけで B_env の当たりのほぼ全てが出る", loc="left", fontsize=10)
    a2.axvline(0, color="#333333", lw=0.8)
    a2.set_yticks(range(len(DIFFS)))
    a2.set_yticklabels([lab for _, lab in DIFFS][::-1], fontsize=9)
    a2.set_xlabel("capture@5% の差、線は 10 km ブロックのブートストラップ 90% 区間")
    a2.set_title("確認の 2 年度 (B2 は淡、B3 は濃): 両方で下限 > 0 なのは\nM_H が M_B を上回ることだけ", loc="left", fontsize=10)
    for s in (a1, a2):
        s.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(Path(out) / "capture-by-role.png", dpi=150)
    plt.close(fig)


def heat(ax, share, lift, title, xt, yt, plt):
    im_ = ax.imshow(np.asarray(share).T * 100, origin="lower", cmap="Purples", vmin=0, vmax=40)
    for b in range(5):
        for h in range(5):
            s = share[b][h] * 100
            if s >= 0.05:
                txt = f"{s:.1f}" + ("" if lift is None or lift[b][h] is None else f"\n×{lift[b][h]:.1f}")
                ax.text(b, h, txt, ha="center", va="center", fontsize=7, color="white" if s > 20 else "#222222")
    ax.set_xticks(range(5))
    ax.set_xticklabels(xt, fontsize=7)
    ax.set_yticks(range(5))
    ax.set_yticklabels(yt, fontsize=7)
    ax.set_title(title, loc="left", fontsize=9)
    return im_


def phase_space(out, plt):
    d = j(out, "phase_space.json")
    q = ["q1", "q2", "q3", "q4", "q5"]
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.4))
    for ax, (y, row) in zip(axes, d["years"].items()):
        r = row["apr_sep"]
        share = [[0] * 5 for _ in range(5)]
        lift = [[None] * 5 for _ in range(5)]
        rate = r["n_pos"] / sum(x["n_cells"] for x in r["bins"])
        for x in r["bins"]:
            share[x["b"] - 1][x["h"] - 1] = x["share"]
            lift[x["b"] - 1][x["h"] - 1] = None if x["rate"] is None else x["rate"] / rate
        heat(ax, share, lift, f"{y} 年 4〜9 月 ({r['n_pos']:,} セル)\n軸: {row['axis_note'].split(':')[0]}、"
             f"Spearman {row['spearman_b_h_all_cells']:.2f}", q, q, plt)
        ax.add_patch(plt.Rectangle((2.5, 2.5), 2, 2, fill=False, ec="#d1176b", lw=1.6))
        ax.set_xlabel("bear-side proxy の 5 分位")
    axes[0].set_ylabel("human-side proxy の 5 分位")
    fig.suptitle("通報のあったセルの 95〜98% は、両方の proxy の上位 40% (赤枠、事前に決めた contact) に入る。"
                 "数字は陽性の割合 (%) と陽性率の倍率", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.01, SOURCE, fontsize=7, color="#444444")
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    fig.savefig(Path(out) / "phase-space.png", dpi=150)
    plt.close(fig)
    p = j(out, "year_shift_posthoc.json")
    lab = ["<0.50", "0.50–0.80", "0.80–0.90", "0.90–0.95", "≥0.95"]
    fig, axes = plt.subplots(1, 5, figsize=(17, 4.2))
    heat(axes[0], p["years"]["2025"]["cell_shares"], None, "全セル (B2 の軸)", lab, lab, plt)
    for ax, y in zip(axes[1:], ("2023", "2024", "2025", "2026")):
        v = p["years"][y]
        heat(ax, v["pos_shares"], None, f"{y} 年 4〜9 月の陽性\n水準の中央値 {v['level']['median']:.3f}、"
             f"寄り {v['lean']['median']:+.3f}", lab, lab, plt)
    for ax in axes:
        ax.set_xlabel("bear-side の percentile")
    axes[0].set_ylabel("human-side の percentile")
    fig.suptitle("上に寄せたビン (結果を見て足した探索): 陽性の約 3 割は両方の上位 5% に、残りは対角の近くに並ぶ。"
                 "数字はその年の陽性 (左端は全セル) の割合 (%)", x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(Path(out) / "phase-space-top.png", dpi=150)
    plt.close(fig)


def year_shift(out, work, art, plt):
    from interface_phase_space import positives

    inside = np.load(Path(art) / "grid_mask.npz")["muni"] >= 0
    pos = positives(art, work, inside)["apr_sep"]
    z = np.load(Path(work) / "scores/b2_confirm_2023-2024_to_2025.npz")
    pb, phh = ph.percentile(z["M_B"].astype(float)), ph.percentile(z["M_H"].astype(float))
    s = j(out, "year_shift.json")["pairs"]["2025_to_2026"]["apr_sep"]
    ph_ = j(out, "year_shift_posthoc.json")["pairs"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, v, name, key in ((axes[0], pb, "bear-side", "cliff_b"), (axes[1], phh, "human-side", "cliff_h")):
        for y, col in ((2025, "#7a8fa6"), (2026, "#d1176b")):
            x = np.sort(v[pos[y]])
            ax.plot(x, np.arange(1, len(x) + 1) / len(x), color=col, lw=1.8, label=f"{y} 年 ({len(x):,} セル)")
        ax.set_xlim(0.5, 1.0)
        ax.set_xlabel(f"{name} proxy の percentile (B2 の軸、2023+2024 で学習)")
        ax.set_ylabel("その値以下の陽性の割合")
        p = s["f3_block"]["p_" + key]
        ax.set_title(f"{name}: Cliff's δ {s[key]:+.3f} (ブロック入れ替え p {p:.3f})\n"
                     f"規則の境 |δ| ≥ 0.147 に届かない", loc="left", fontsize=9)
        ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax = axes[2]
    pairs = [("2023_to_2024", "2023→24"), ("2024_to_2025", "2024→25"), ("2025_to_2026", "2025→26")]
    for i, (k, lab) in enumerate(pairs):
        r = ph_[k]
        ax.bar(i - 0.18, r["cliff_level"], 0.34, color="#5b2a86", label="水準 (b+h)/2" if i == 0 else None)
        ax.bar(i + 0.18, r["cliff_lean"], 0.34, color="#e0a96d", label="寄り b−h (+ は bear-side 寄り)" if i == 0 else None)
        for dx, key in ((-0.18, "cliff_level"), (0.18, "cliff_lean")):
            ax.text(i + dx, r[key] + (0.006 if r[key] >= 0 else -0.012), f"p {r['f3_block_p'][key]:.3f}",
                    ha="center", fontsize=7)
    ax.axhline(0, color="#333333", lw=0.8)
    for t in (0.147, -0.147):
        ax.axhline(t, color="#999999", lw=0.8, ls=":")
    ax.set_xticks(range(3))
    ax.set_xticklabels([lab for _, lab in pairs])
    ax.set_ylabel("Cliff's δ (後の年度 − 前の年度)")
    ax.set_ylim(-0.2, 0.12)
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    ax.set_title("水準と寄り (探索、各組の残り 2 年度で学習した軸)\n点線は小さい効果の境", loc="left", fontsize=9)
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
    fig.suptitle("2025 → 2026 で通報のセルは両方の proxy の少し低い所へ動いた。どちらか一方の側へ寄ったのではない",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(Path(out) / "year-shift.png", dpi=150)
    plt.close(fig)


def falsification(out, plt):
    f1 = [j(out, f"f1_role_perm_{s}.json") for s in ("b2", "b3")]
    f2 = j(out, "f2_block_shuffle.json")
    keys = [("abs_cap_diff", "|capture@5% の差|"), ("spearman", "2 つの軸の Spearman"), ("jsd_pos_vs_cells", "陽性と全セルの JSD")]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
    for ax, (k, lab) in zip(axes, keys):
        for i, (d, name) in enumerate(zip(f1, ("B2 (2025)", "B3 (2026)"))):
            vals = [p[k] for p in d["perms"]]
            ax.scatter(vals, np.full(len(vals), i) + np.random.default_rng(i).uniform(-0.12, 0.12, len(vals)),
                       s=14, color="#9aa5b1", label="無作為の分け方 20 通り" if i == 0 else None)
            ax.scatter([d["real"][k]], [i], s=70, marker="D", color="#d1176b", label="本物の B / H" if i == 0 else None)
            ax.text(d["real"][k], i + 0.22, f"{d['rank_of_real_among_21'][k]} 位 / 21", fontsize=7, ha="center")
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["B2 (2025)", "B3 (2026)"])
        ax.set_ylim(-0.6, 1.6)
        ax.set_title(f"F1: {lab}", loc="left", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(fontsize=7, frameon=False, loc="lower right")
    ax = axes[3]
    years = list(f2["years"])
    ax.bar(np.arange(4) - 0.18, [f2["years"][y]["observed"]["contact_share"] for y in years], 0.34, color="#5b2a86", label="本物")
    ax.bar(np.arange(4) + 0.18, [f2["years"][y]["null"]["contact_share"]["0.5"] for y in years], 0.34, color="#9aa5b1",
           label="10 km ブロックごとに移した 200 回の中央値")
    ax.set_xticks(range(4))
    ax.set_xticklabels(years)
    ax.set_ylim(0, 1.3)
    ax.set_title("F2: 陽性のうち contact に入る割合", loc="left", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("反証: B と H の名前の付いた分け方は、無作為の分け方と比べて何が違うか (F1)、陽性の位置を崩すと偏りは残るか (F2)",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(Path(out) / "falsification.png", dpi=150)
    plt.close(fig)


def reporting(out, plt):
    d = j(out, "reporting_process.json")["years"]
    ys = list(d)
    rows = [("秋田市の通報の割合", [d[y]["akita_city_report_share"] for y in ys], "{:.1%}"),
            ("1 セルあたりの通報の数", [d[y]["reports_per_cell"] for y in ys], "{:.3f}"),
            ("目撃の割合 (info_type)", [d[y]["info_type_share"].get("目撃", 0) for y in ys], "{:.1%}"),
            ("human-side の第 5 分位の通報の割合", [d[y]["top_human_quintile_report_share"] for y in ys], "{:.1%}")]
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.6))
    for ax, (lab, v, fmt) in zip(axes, rows):
        ax.bar(ys, v, color=["#9aa5b1"] * 3 + ["#d1176b"])
        for x, val in zip(ys, v):
            ax.text(x, val, fmt.format(val), ha="center", va="bottom", fontsize=8)
        ax.set_title(lab, loc="left", fontsize=9)
        ax.set_ylim(0, max(v) * 1.2)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.set_yticks([])
    fig.suptitle("4〜9 月の通報の構成: 2026 年は秋田市の割合だけが大きく変わった (R040 の値を 2023 年まで延ばした)",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(Path(out) / "reporting.png", dpi=150)
    plt.close(fig)


def phase_map(out, work, art, plt):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bear-synthesis/scripts"))
    import mapkit as mk
    from interface_phase_space import positives
    from matplotlib.lines import Line2D
    from trial_maps import draw_classes, outline

    meta = json.loads((Path(art) / "grid.json").read_text(encoding="utf-8"))
    inside = np.load(Path(art) / "grid_mask.npz")["muni"] >= 0
    iy0, ix0 = np.nonzero(inside)
    xc = meta["x0"] + (ix0 + 0.5) * meta["size"]
    yc = meta["y0"] + (iy0 + 0.5) * meta["size"]
    pos = positives(art, work, inside)["apr_sep"]
    z = np.load(Path(work) / "scores/b2_confirm_2023-2024_to_2025.npz")
    pb, phh = ph.percentile(z["M_B"].astype(float)), ph.percentile(z["M_H"].astype(float))
    hb, hh = pb >= 0.9, phh >= 0.9
    cls = np.zeros(len(pb), np.int16)
    cls[hb & ~hh], cls[~hb & hh], cls[hb & hh] = 1, 2, 3
    full = (meta["x0"], meta["x0"] + meta["nx"] * meta["size"], meta["y0"], meta["y0"] + meta["ny"] * meta["size"])
    areas, pref = mk.background(full, "EPSG:6678", "05")
    colours = ["#a8d5b5", "#f2c38f", "#b9a3d6"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 8.6))
    record = {}
    for ax, y in zip(axes, (2025, 2026)):
        mk.cm.draw_areas_under(ax, areas)
        draw_classes(ax, meta, inside, cls, colours, "antialiased")
        mk.cm.draw_areas_over(ax, areas)
        m = pos[y]
        ax.scatter(xc[m], yc[m], s=2.0, c="#111111", lw=0, zorder=5, rasterized=True)
        outline(ax, pref, "秋田市", color="#d1176b", lw=1.2)
        mk.finish(ax, full)
        sh = {k: float(((cls == v) & m).sum() / m.sum()) for k, v in (("none", 0), ("bear_only", 1), ("human_only", 2), ("both", 3))}
        record[str(y)] = sh
        ax.set_title(f"{y} 年 4〜9 月 ({int(m.sum()):,} セル)\n両方 {sh['both']:.1%}、bear-side だけ {sh['bear_only']:.1%}、"
                     f"human-side だけ {sh['human_only']:.1%}、どちらも外 {sh['none']:.1%}", loc="left", fontsize=10)
    handles = [Line2D([], [], marker="s", ls="", color=colours[2], ms=8, label=f"両方の proxy が上位 10% ({int((cls == 3).sum()):,} セル)"),
               Line2D([], [], marker="s", ls="", color=colours[0], ms=8, label=f"bear-side だけ上位 10% ({int((cls == 1).sum()):,})"),
               Line2D([], [], marker="s", ls="", color=colours[1], ms=8, label=f"human-side だけ上位 10% ({int((cls == 2).sum()):,})"),
               Line2D([], [], marker="o", ls="", color="#111111", ms=4, label="通報のあったセル"),
               Line2D([], [], color="#d1176b", lw=1.2, label="秋田市の境")]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.03))
    fig.suptitle("B2 の軸 (2023+2024 年度で学習) の上位 10% で塗った秋田県: 通報は両方が高い帯 (紫) に沿って出る",
                 x=0.02, ha="left", fontsize=12)
    fig.text(0.02, 0.008, SOURCE + "。市町村界 jp-admin-2026-09。軸はモデルのスコアで、熊や人の密度ではない。", fontsize=7, color="#444444")
    fig.tight_layout(rect=(0, 0.08, 1, 0.97))
    fig.savefig(Path(out) / "map-phase-classes.png", dpi=150)
    plt.close(fig)
    json.dump(record, open(Path(out) / "map_phase_classes.json", "w", encoding="utf-8"), indent=1)


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("art", type=Path)
    a.add_argument("work", type=Path)
    a.add_argument("out", type=Path)
    a.add_argument("--only", nargs="*")
    args = a.parse_args()
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
    todo = {"capture": lambda: capture_by_role(args.out, plt), "phase": lambda: phase_space(args.out, plt),
            "shift": lambda: year_shift(args.out, args.work, args.art, plt), "falsification": lambda: falsification(args.out, plt),
            "reporting": lambda: reporting(args.out, plt), "map": lambda: phase_map(args.out, args.work, args.art, plt)}
    for k, f in todo.items():
        if not args.only or k in args.only:
            f()
            print("drew", k, flush=True)


if __name__ == "__main__":
    main()
