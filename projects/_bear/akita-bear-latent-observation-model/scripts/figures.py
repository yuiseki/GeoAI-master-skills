"""The report's figures, drawn from the saved outputs (JSON) and the posterior summaries of b; nothing is refitted.

    gates.png       the staged gates (2a, 2, 3): correct and false-detection rates against the 0.8 / 0.2 lines,
                    and how T_B and T_R were called in S1 and S2
    cv.png          cross-source gains L2 - L0H (default, wide, all 549 meshes) and the F1 / F2 block shuffles
    latent-b.png    posterior mean and sd of the latent bear space-use score b (L2, default) on the 5 km meshes
    voi.png         value of extra data: S1/S2 correct and S3/S5 false-bear rates per candidate (needs voi_summary.json)

From repository root:
    uvx --with numpy==2.5.4 --with matplotlib python \
      projects/_bear/akita-bear-latent-observation-model/scripts/figures.py \
      projects/_bear/akita-bear-latent-observation-model/outputs artifacts/_bear/akita-bear-latent-observation-model
"""

import argparse
import json
from pathlib import Path

import numpy as np

C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"  # categorical slots 1-3 (reference palette)
INK, MUTED = "#0b0b0b", "#52514e"
STAGES = [("2a", "段階 2a: L3 (クマダスの年の状態)"), ("2", "段階 2: 時期ごとの状態"), ("3", "段階 3: OU の遷移")]
SOURCE = ("合成データ: 実データの 480 core mesh、共変量、市町村、観測の時期で生成。実データ: 環境省の分布メッシュ yo4 "
          "rev 7f635cb、クマダス 4〜9 月 2023〜2026 年")


def mesh_bounds(code):
    """(west, south, east, north) in degrees of an 8-digit 5 km mesh code (2nd-order code + quarter 22/27/72/77)."""
    p, u, q, v, r, w = int(code[:2]), int(code[2:4]), int(code[4]), int(code[5]), int(code[6]), int(code[7])
    s = p / 1.5 + q * 5 / 60 + (r // 5) * 2.5 / 60
    west = 100 + u + v * 7.5 / 60 + (w // 5) * 3.75 / 60
    return west, s, west + 3.75 / 60, s + 2.5 / 60


def j(d, name):
    return json.load(open(Path(d) / name, encoding="utf-8"))


def gates(out, plt):
    s = j(out, "summary_gates_falsification.json")["stages"]
    rows = [("S1_correct", "S1 正答", 0.8), ("S2_correct", "S2 正答", 0.8), ("S4_correct", "S4 正答", 0.8),
            ("S3_false_bear", "S3 熊側の誤検出", 0.2), ("S5_false_bear", "S5 熊側の誤検出", 0.2)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1.2, 1]})
    x = np.arange(len(rows))
    for k, ((st, lab), c) in enumerate(zip(STAGES, (C1, C2, C3))):
        a1.bar(x + (k - 1) * 0.27, [s[st][r] for r, _, _ in rows], 0.25, color=c, label=lab)
    for i, (_, _, t) in enumerate(rows):
        a1.plot([i - 0.42, i + 0.42], [t, t], color=INK, lw=1, ls=":")
    a1.set_xticks(x, [lab for _, lab, _ in rows], fontsize=9)
    a1.set_ylim(0, 1)
    a1.set_ylabel("seed の割合 (収束しない当てはめは失敗)", fontsize=9)
    a1.legend(fontsize=8, frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.1))
    a1.set_title("点線が関門 (正答は 0.8 以上、誤検出は 0.2 以下)。どの段も通らない", loc="left", fontsize=10)
    cats = [("1", "+", C1), ("0", "検出なし", "#c9c8c3"), ("-1", "−", C2)]
    labels, y = [], 0
    for st, lab in STAGES:
        for sc in ("S1", "S2"):
            for q, key in enumerate(("T_B", "T_R")):
                left = 0
                for v, name, c in cats:
                    n = s[st]["detect_counts"][sc][key][v]
                    a2.barh(y, n, left=left, color=c, height=0.8, label=name if y == 0 else None)
                    left += n
                labels.append(f"{st} {sc} {key}")
                y += 1
        y += 0.6
    pos = [i + 0.6 * (i // 4) for i in range(len(labels))]
    a2.set_yticks(pos, labels, fontsize=8)
    a2.invert_yaxis()
    a2.set_xlabel("seed の数 (20 本)", fontsize=9)
    a2.legend(fontsize=8, frameon=False, loc="lower right", ncol=3, bbox_to_anchor=(1, -0.32))
    a2.set_title("S1 は熊側だけ、S2 は通報だけが変わる。真値は S1 で T_B +、S2 で T_R +\n"
                 "段階 3 は両方で T_R + と T_B − を出し、2 つを同じに見る", loc="left", fontsize=9)
    fig.suptitle("識別可能性の関門: 熊側の変化と通報の過程の変化は分けられない", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.005, SOURCE, fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(Path(out) / "gates.png", dpi=150)


def cv(out, plt):
    runs = [("real_cv_default.json", "default"), ("real_cv_wide.json", "wide"), ("real_cv_allmesh.json", "549 メッシュ")]
    f = j(out, "summary_gates_falsification.json")["falsification"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, w, title in zip(axes, ("E", "Y"), ("環境省の記録を隠す", "クマダスの件数を隠す")):
        for k, (fn, lab) in enumerate(runs):
            g = j(out, fn)["gains"][f"{w}: L2 - L0H"]
            ax.plot([g["lo90"], g["hi90"]], [k, k], color=C1, lw=2.2)
            ax.plot(g["sum"], k, "o", color=C1, ms=6)
            ax.text(g["hi90"], k - 0.22, f"{g['sum']:+.1f}", fontsize=8, color=INK)
        sh = f["F1"][f"shuffled_{w}_gain"]
        ax.plot(sh, [len(runs)] * len(sh), "o", color=C2, ms=6, alpha=0.75, mec="white", mew=1)
        ax.axvline(0, color=INK, lw=0.8)
        ax.set_yticks(range(len(runs) + 1), [lab for _, lab in runs] + ["F1: 記録を移した 10 本"], fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel("L2 − L0H の対数予測密度の差 (メッシュの合計、90% はブロックのブートストラップ)", fontsize=8)
        ax.set_title(title, loc="left", fontsize=10)
    lam = f["F2"]
    fig.suptitle("観測系をまたぐ検証: 共有の b は隠した記録を共変量と H だけより良く予測しない。"
                 f"F2: 記録を移すと λ_E は {lam['real_lam_E']['mean']:.2f} から中央値 {lam['shuffled_lam_E_mean_median']:.2f} へ",
                 x=0.01, ha="left", fontsize=10)
    fig.text(0.01, 0.005, SOURCE, fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    fig.savefig(Path(out) / "cv.png", dpi=150)


def latent_b(out, work, plt):
    from matplotlib.collections import PatchCollection
    from matplotlib.patches import Rectangle

    z = np.load(Path(work) / "fit/real_full_default_L2_b.npz", allow_pickle=True)
    rects = [Rectangle((w, s), e - w, n - s) for w, s, e, n in (mesh_bounds(str(c)) for c in z["mesh_code"])]
    fig, axes = plt.subplots(1, 2, figsize=(11, 7.2))
    for ax, v, cmap, lab in zip(axes, (z["b_mean"], z["b_sd"]), ("BuGn", "Greys"),
                                ("事後平均 (標準化した潜在の尺度)", "事後の標準偏差 (不確かさ)")):
        pc = PatchCollection(rects, cmap=cmap, edgecolor="white", linewidth=0.3)
        pc.set_array(np.asarray(v, float))
        ax.add_collection(pc)
        ax.autoscale_view()
        ax.set_aspect(1 / np.cos(np.radians(39.7)))
        ax.set_xlabel("経度", fontsize=8)
        ax.set_ylabel("緯度", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.set_title(lab, loc="left", fontsize=10)
        fig.colorbar(pc, ax=ax, shrink=0.6)
    fig.suptitle("複数観測系から推定した latent bear space-use score (L2、480 の 5 km メッシュ)\n"
                 "熊の生息域や密度ではない。観測系をまたぐ検証では予測の得が無かった", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.002, "L2 = 共有の静的な b + 人側の測定 H、4 chain × 1,000 draw。" + SOURCE, fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    fig.savefig(Path(out) / "latent-b.png", dpi=150)


def voi(out, plt):
    v = j(out, "voi_summary.json")
    names = ["baseline", "V1", "V2", "V3", "V4", "V5", "V6"]
    lab = {"baseline": "追加なし", "V1": "V1 固定カメラ", "V2": "V2 努力付きカメラ", "V3": "V3 捕獲と努力",
           "V4": "V4 環境省方式 2023/2026", "V5": "V5 運用の履歴 (強い仮定)", "V6": "V6 時系列の H"}
    names = [n for n in names if n in v]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    y = np.arange(len(names))
    a1.barh(y - 0.2, [v[n]["S1_correct"] for n in names], 0.38, color=C1, label="S1 正答 (熊側だけ)")
    a1.barh(y + 0.2, [v[n]["S2_correct"] for n in names], 0.38, color=C2, label="S2 正答 (通報だけ)")
    a2.barh(y - 0.2, [v[n]["S3_false_bear"] for n in names], 0.38, color=C1, label="S3 (人側だけ)")
    a2.barh(y + 0.2, [v[n]["S5_false_bear"] for n in names], 0.38, color=C2, label="S5 (変化なし)")
    a1.axvline(0.8, color=INK, lw=1, ls=":")
    a2.axvline(0.2, color=INK, lw=1, ls=":")
    a1.set_yticks(y, [lab[n] for n in names], fontsize=9)
    a1.invert_yaxis()
    for ax, t in ((a1, "正しい判定の割合 (点線 0.8)"), (a2, "熊側の変化の誤検出か失敗の割合 (点線 0.2)")):
        ax.set_xlim(0, 1)
        ax.set_title(t, loc="left", fontsize=10)
        ax.legend(fontsize=8, frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.1))
    fig.suptitle(f"追加のデータの価値 (合成、L3 + そのデータ、seed 0〜{v['seeds'] - 1})", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.005, "V5 は「通報の過程の変化は全て記録された運用の変化」という強い仮定に依存する", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    fig.savefig(Path(out) / "voi.png", dpi=150)


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("out", type=Path)
    a.add_argument("work", type=Path)
    args = a.parse_args()
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
    gates(args.out, plt)
    cv(args.out, plt)
    latent_b(args.out, args.work, plt)
    if (args.out / "voi_summary.json").exists():
        voi(args.out, plt)


if __name__ == "__main__":
    main()
