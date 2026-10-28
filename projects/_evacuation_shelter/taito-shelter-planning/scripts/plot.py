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
    flood = [int(row["flood_rank_cap"]) for row in rows]
    coverage = [float(row["coverage_percent"]) for row in rows]
    title = "浸水リスクをどこまで許すと、近くに拠点を置けるか"
    xlabel = "浸水ランク合計の上限"
    ylabel = "400 m 以内の人口割合 (%)"
    font = use_cjk_font(title + xlabel + ylabel + "13拠点 34個のパレート解から4点")

    fig, ax = plt.subplots(figsize=(8.6, 5.5))
    ax.plot(flood, coverage, color="#0072B2", marker="o", markersize=8, linewidth=2)
    for x, y in zip(flood, coverage, strict=True):
        ax.annotate(
            f"{y:.1f}%", (x, y), xytext=(0, 9), textcoords="offset points", ha="center"
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xlim(-1, 35)
    ax.set_ylim(0, 60)
    ax.set_xticks(flood)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    fig.text(
        0.99,
        0.01,
        "13拠点。34個のパレート解から、元事例が示した4点を掲載",
        ha="right",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUTPUT / "shelter-tradeoff.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    metadata = {
        "question": title,
        "kind": "relationship",
        "source_values": "outputs/source-values.csv",
        "source": (
            "study-geoai-algo-py/case-studies/002-shelter-planning/README.md "
            "and src/012-B-epsilon-constraint/README.md"
        ),
        "source_commit": SOURCE_COMMIT,
        "source_rows": len(rows),
        "data_version": "実験結果 2026-09-29。人口は WorldPop 2025",
        "n": {"open_sites": 13, "pareto_solutions_total": 34, "shown": 4},
        "interval_meaning": (
            "区間は描いていない。線は選抜した4点を結ぶ案内線で、未掲載点を補間しない"
        ),
        "axes": {"x": "浸水ランク合計の上限", "y": "400 m 以内の人口割合 (%)"},
        "axis_limits": {"x": [-1, 35], "y": [0, 60]},
        "font": font,
        "generated_on": "2026-10-23",
        "limitation": (
            "全34点の形と各候補地の位置は、元コードの front-taito.png と"
            "配置出力の方が詳しい"
        ),
    }
    (OUTPUT / "shelter-tradeoff.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
