"""Collect, from the saved outputs of the _bear projects, every held-out difference in capture@5% between the
static environment-only map (B_env) and B_env with something added, and draw them on one axis. Nothing is
recomputed: each number is read from the JSON that the original run wrote.

From repository root:
    uvx --with matplotlib --with pandas python projects/_bear/bear-synthesis/scripts/added_predictors.py \
      projects/_bear projects/_bear/bear-synthesis/outputs
"""

import argparse
import json
from collections import namedtuple
from pathlib import Path

Comparison = namedtuple("Comparison", "label year role file path")

GRID = "akita-bear-risk-grid-100m/outputs/"
MAST = "akita-bear-mast-exposure/outputs/"
COMPARISONS = [
    Comparison("過去の通報を特徴量に足す", 2025, "confirmation",
               GRID + "b2_confirm_2023-2024_to_2025.json", ("diff_capture@5%", "M_full - B_env")),
    Comparison("過去の通報を特徴量に足す", 2026, "confirmation",
               GRID + "b3_confirm_2023-2025_to_2026.json", ("diff_capture@5%", "M_full - B_env")),
    Comparison("年の豊凶 × ブナ・ナラ類の割合", 2025, "confirmation",
               MAST + "b3_confirm.json", ("targets", "2025", "retrospective", "M5", "diff_capture@5%")),
    Comparison("年の豊凶 × ブナ・ナラ類の割合", 2026, "confirmation",
               MAST + "b3_confirm.json", ("targets", "2026", "retrospective", "M5", "diff_capture@5%")),
    Comparison("同 (cross-fit の B_env)", 2025, "diagnostic",
               MAST + "x2_crossfit_beta.json", ("targets", "2025", "retrospective", "cross_fit", "diff_capture@5%")),
    Comparison("同 (cross-fit の B_env)", 2026, "diagnostic",
               MAST + "x2_crossfit_beta.json", ("targets", "2026", "retrospective", "cross_fit", "diff_capture@5%")),
    Comparison("季節内の活性化 (県全体、翌週)", 2026, "confirmation",
               GRID + "seasonal_activation.json", ("years", "2026", "intervals_90", "M_minus_E")),
    Comparison("季節内の活性化 (県全体、翌週)", 2024, "diagnostic",
               GRID + "akita_city_activation_2024.json", ("intervals_90", "statewide_M_minus_E")),
    Comparison("季節内の活性化 (秋田市の陽性、県の上位 5%)", 2024, "confirmation",
               GRID + "akita_city_activation_2024.json", ("intervals_90", "primary_city_M_minus_E")),
    Comparison("季節内の活性化 (秋田市の中の上位 5%)", 2024, "diagnostic",
               GRID + "akita_city_activation_2024.json", ("intervals_90", "city_budget_M_minus_E")),
]


def pick(obj, path):
    for key in path:
        obj = obj[key]
    return obj


def triple(v):
    """(difference, lower, upper) from {"diff", "lo90", "hi90"} or [diff, lo, hi]."""
    if isinstance(v, dict):
        return v["diff"], v["lo90"], v["hi90"]
    d, lo, hi = v
    return d, lo, hi


def rows(root):
    root = Path(root)
    cache = {}
    out = []
    for c in COMPARISONS:
        if c.file not in cache:
            cache[c.file] = json.loads((root / c.file).read_text(encoding="utf-8"))
        d, lo, hi = triple(pick(cache[c.file], c.path))
        out.append({"label": c.label, "year": c.year, "role": c.role, "diff": d, "lo90": lo, "hi90": hi,
                    "source": c.file + "#" + "/".join(c.path)})
    return out


def plot(table, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]
    n = len(table)
    fig, ax = plt.subplots(figsize=(8.6, 0.42 * n + 1.4))
    for i, r in enumerate(table):
        y = n - 1 - i
        colour = "#2b6cb0" if r["role"] == "confirmation" else "#999999"
        ax.plot([r["lo90"], r["hi90"]], [y, y], color=colour, lw=2)
        ax.plot(r["diff"], y, "o", color=colour, ms=6, mfc=colour if r["role"] == "confirmation" else "white")
        ax.text(0.081, y, f"{r['diff']:+.4f}", va="center", fontsize=8, color=colour)
    ax.axvline(0, color="#333333", lw=0.8)
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{r['label']}  {r['year']}" for r in table][::-1], fontsize=9)
    ax.set_xlim(-0.08, 0.1)
    ax.set_xlabel("capture@5% の差 (足したもの − B_env)、線は 90% 区間")
    ax.set_title("B_env に何を足しても、学習に使っていない年度で下限が 0 を超えない\n"
                 "青は規則を先に決めた確認、灰色は診断", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main():
    import pandas as pd

    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("root", type=Path)
    a.add_argument("out", type=Path)
    args = a.parse_args()
    table = rows(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(table).to_csv(args.out / "added_predictors.csv", index=False)
    plot(table, args.out / "added-predictors.png")
    for r in table:
        print(r["label"], r["year"], r["role"], round(r["diff"], 4), round(r["lo90"], 4), round(r["hi90"], 4))


if __name__ == "__main__":
    main()
