"""Rank correlations of the autumn reports with each weather measure: the planned test (H1, dT), the falsification
(the future dT) and the exploration, with the prefecture-level correlations as dots and the permutation p beside.

Usage:
    uvx --with matplotlib python plot_rho.py H1.json EXPLORE.json OUT.png
"""

import json
import sys

EXPLORE = [("T_now", "当年の夏の気温"), ("T_last", "前年の夏の気温"), ("T_yoy", "気温の前年比"), ("SRF_now", "当年の夏の日射"),
           ("SRF_last", "前年の夏の日射"), ("SRF_yoy", "日射の前年比"), ("P_now", "当年の夏の降水"), ("P_last", "前年の夏の降水")]
REGIONS = [("akita", "秋田", "#c4512a"), ("gifu", "岐阜", "#3b6e8f"), ("kyoto", "京都", "#6a8f3b"), ("ishikawa", "石川", "#8a5a9e")]


def rows(h1, explore):
    """[{key, label, rho, p, p_kind, regions}] in the order of the figure."""
    out = [{"key": "H1", "label": "H1: ΔT (前年 − 前々年の夏)", "rho": h1["H1"]["rho"], "p": h1["H1"]["p_perm_one_sided"],
            "p_kind": "片側", "regions": h1["H1"]["per_region_rho"]},
           {"key": "future_dT", "label": "反証: 未来の ΔT", "rho": h1["falsification_future_dT"]["rho"],
            "p": h1["falsification_future_dT"]["p_two_sided"], "p_kind": "両側", "regions": {}}]
    m = explore["measures"]
    missing = [k for k, _ in EXPLORE if k not in m]
    if missing:
        raise SystemExit(f"no {missing} in the exploration")
    for k, label in EXPLORE:
        out.append({"key": k, "label": f"探索: {label}", "rho": m[k]["rho"], "p": m[k]["p_two_sided"], "p_kind": "両側",
                    "regions": m[k]["per_region_rho"]})
    return out


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    h1, ex, out = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
    rs = rows(h1, ex)
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    ys = list(range(len(rs)))[::-1]
    for y, r in zip(ys, rs):
        ax.barh(y, r["rho"], 0.55, color="#1f4e79" if r["key"] == "H1" else "#b8c4d0")
        for k, (reg, _, col) in enumerate(REGIONS):
            if reg in r["regions"]:
                ax.plot(r["regions"][reg], y + (k - 1.5) * 0.12, "o", ms=4, color=col, zorder=3)
        ax.text(1.08, y, f"{r['rho']:+.3f}  p {r['p']:.3f} ({r['p_kind']})", va="center", fontsize=8)
    ax.set_yticks(ys, [r["label"] for r in rs], fontsize=9)
    ax.axvline(0, color="#444444", lw=0.8)
    ax.set_xlim(-1.05, 1.05)
    ax.set_xlabel("秋の通報 (県の中の偏差) との順位相関。棒は 32 の県 × 年、点は県ごと")
    for _, name, col in REGIONS:
        ax.plot([], [], "o", color=col, label=name)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.11), fontsize=8, frameon=False, ncol=4, title="県ごとの順位相関", title_fontsize=8)
    ax.set_title("夏の気象と秋の通報の順位相関 (多重比較の目安 p < 0.0056 に届いたものは無い)", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")


if __name__ == "__main__":
    main()
