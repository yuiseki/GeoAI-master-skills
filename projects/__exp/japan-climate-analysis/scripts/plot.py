import csv
import importlib.util
import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
OUTPUT = PROJECT / "outputs"
SOURCE_COMMIT = "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
FONT_HELPER = ROOT / ".agents/skills/analysis-visualize/scripts/cjk_font.py"
SPEC = importlib.util.spec_from_file_location("cjk_font", FONT_HELPER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load font helper: {FONT_HELPER}")
CJK_FONT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CJK_FONT)
use_cjk_font = CJK_FONT.use_cjk_font


def main():
    rows = list(csv.DictReader((OUTPUT / "source-values.csv").open()))
    methods = ["平年値区間", "分位点 GBDT", "CQR"]
    title = "90%予測区間は、関東の降水量と気温をどれだけ覆ったか"
    xlabel = "予測区間の作り方"
    ylabel = "試験期間の被覆率 (%)"
    font = use_cjk_font(
        title + xlabel + ylabel + "降水量気温名目水準" + "".join(methods)
    )

    fig, ax = plt.subplots(figsize=(9.2, 5.8))
    for variable, color, marker in [
        ("降水量", "#0072B2", "o"),
        ("気温", "#D55E00", "s"),
    ]:
        part = {
            row["method"]: float(row["coverage_percent"])
            for row in rows
            if row["variable"] == variable
        }
        values = [part[method] for method in methods]
        ax.plot(
            range(len(methods)),
            values,
            marker=marker,
            color=color,
            linewidth=2,
            markersize=8,
            label=variable,
        )
        offset = 8 if variable == "降水量" else -18
        for x, value in enumerate(values):
            ax.annotate(
                f"{value:.1f}%",
                (x, value),
                xytext=(0, offset),
                textcoords="offset points",
                ha="center",
            )
    ax.axhline(90, color="#555555", linestyle="--", linewidth=1.5, label="名目水準 90%")
    ax.set_xticks(range(len(methods)), methods)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 100)
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.25)
    fig.text(
        0.99,
        0.01,
        "n=39,720格子月。ただし独立な標本は約120か月",
        ha="right",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUTPUT / "interval-coverage.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    metadata = {
        "question": title,
        "kind": "comparison",
        "source_values": "outputs/source-values.csv",
        "source": "study-geoai-algo-py/case-studies/006-japan-climate/README.md",
        "source_commit": SOURCE_COMMIT,
        "source_rows": len(rows),
        "data_version": "AgERA5 1979-01〜2025-12。実験結果 2026-09-29",
        "n": {"grid_month_rows": 39720, "approximately_independent_months": 120},
        "interval_meaning": (
            "各点は2016〜2025年の90%予測区間の被覆率。モデル間の不確かさ区間ではない"
        ),
        "axes": {"x": "予測区間の作り方", "y": "試験期間の被覆率 (%)"},
        "axis_limits": {"y": [0, 100]},
        "font": font,
        "generated_on": "2026-10-23",
        "limitation": (
            "月ごとの被覆率は示さないため、元コードの coverage.png の方が"
            "季節差を詳しく読める"
        ),
    }
    (OUTPUT / "interval-coverage.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
