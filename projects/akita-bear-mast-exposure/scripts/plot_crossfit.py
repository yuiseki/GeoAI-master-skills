"""Figure of the cross-fit diagnostic, from outputs/x2_crossfit_beta.json: crossfit-beta-and-capture.png.

    uvx --with matplotlib python projects/akita-bear-mast-exposure/scripts/plot_crossfit.py projects/akita-bear-mast-exposure/outputs
"""

import json
import sys


def rows(x, variant="retrospective"):
    """[(target, beta in-sample, se, beta cross-fit, se, diff, lo90, hi90)]"""
    out = []
    for t, r in x["targets"].items():
        a, b = r[variant]["in_sample_original"], r[variant]["cross_fit"]
        d = b["diff_capture@5%"]
        out.append((t, a["fit"]["beta"], a["fit"]["se_beta"], b["fit"]["beta"], b["fit"]["se_beta"], d["diff"], d["lo90"], d["hi90"]))
    return out


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    o = sys.argv[1]
    x = json.load(open(f"{o}/x2_crossfit_beta.json"))
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    rr = rows(x)
    for i, (t, bi, si, bc, sc, d, lo, hi) in enumerate(rr):
        axes[0].errorbar([i - 0.12], [bi], yerr=[1.96 * si], fmt="o", color="#8a9bb0", label="in-sample の offset (元)" if i == 0 else None)
        axes[0].errorbar([i + 0.12], [bc], yerr=[1.96 * sc], fmt="o", color="#c4512a", label="cross-fit の offset" if i == 0 else None)
        axes[1].plot([i], [d * 100], "o", color="#c4512a")
        axes[1].plot([i, i], [lo * 100, hi * 100], "-", color="#c4512a", lw=2)
    for ax in axes:
        ax.axhline(0, color="#444444", lw=0.7)
        ax.set_xticks(range(len(rr)), [f"{r[0]} 年度" for r in rr])
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_title("β (線は ±1.96 SE)", fontsize=10, loc="left")
    axes[0].legend(fontsize=8, frameon=False, loc="lower left")
    axes[1].set_title("cross-fit の β で並べた capture@5% − B_env (ポイント、90% 区間)", fontsize=10, loc="left")
    fig.suptitle("offset を cross-fit にすると β は 0 から離れるが、目的の年の上位 5% は良くならない (retrospective)", x=0.02, ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{o}/crossfit-beta-and-capture.png", dpi=150, bbox_inches="tight")


if __name__ == "__main__":
    main()
