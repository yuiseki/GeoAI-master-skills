"""Plot already computed screening results; do not recompute the analysis.

Run: uvx --with matplotlib python projects/__exp/hokkaido-forest-biomass-survey/scripts/plot.py
"""

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
sys.path.insert(0, str(ROOT / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402


def ids(items):
    return {(item["cell_row"], item["cell_col"]) for item in items}


def classify_sets(summary):
    main = ids(summary["variants"]["forest_0_8_main"])
    stable = ids(summary["stable_main_ids"])
    raw = ids(summary["variants"]["raw"])
    if not stable <= main:
        raise ValueError("stable candidates must be in main top list")
    return {"stable": stable, "main_other": main - stable, "raw_only": raw - main}


def main():
    summary_path = PROJECT / "outputs/summary.json"
    cells_path = PROJECT / "outputs/cell_metrics.csv"
    summary = json.loads(summary_path.read_text())
    categories = classify_sets(summary)
    with cells_path.open(newline="") as fh:
        records = list(csv.DictReader(fh))
    points = {(int(r["cell_row"]), int(r["cell_col"])): r for r in records}
    for group in categories.values():
        if not group <= points.keys():
            raise ValueError("candidate missing from cell metrics")
    font = use_cjk_font("北海道東部 推定AGB低下 現地照合 候補 安定 主条件のみ 生の上位のみ 経度 緯度 背景 点 年 位置図")
    fig, ax = plt.subplots(figsize=(9, 8), constrained_layout=True)
    background = [r for r in records if float(r["cover_frac"]) >= 0.95 and
                  float(r["forest_frac"]) >= 0.8 and float(r["drop"]) > 0 and
                  int(r["valid_pixels_2010"]) >= 80 and int(r["valid_pixels_2025"]) >= 80]
    ax.scatter([float(r["lon"]) for r in background], [float(r["lat"]) for r in background],
               s=3, c="#d2d2d2", alpha=0.55, linewidths=0,
               label=f"主条件に適合 ({len(background)})")
    styles = [
        ("raw_only", "#b45f06", "生の上位のみ", "x", 78),
        ("main_other", "#157f9b", "主条件のみ", "o", 80),
        ("stable", "#8e2675", "設定を変えても残る", "o", 115),
    ]
    for key, color, label, marker, size in styles:
        rows = [points[id] for id in sorted(categories[key])]
        edge = {"edgecolors": "white", "linewidths": 0.8} if marker == "o" else {"linewidths": 1.4}
        ax.scatter([float(r["lon"]) for r in rows], [float(r["lat"]) for r in rows],
                   s=size, marker=marker, c=color, zorder=3, label=f"{label} ({len(rows)})", **edge)
    ax.set(xlabel="経度 (度)", ylabel="緯度 (度)", title="北海道東部の現地照合候補：モデル上のAGB低下")
    ax.set_aspect(1 / 0.73)
    ax.grid(alpha=0.2)
    ax.legend(loc="lower left", framealpha=0.95)
    fig.text(0.5, -0.01, "点は集計面の中心。森林の実測減少や行政境界は示さない。",
             ha="center", fontsize=9)
    output = PROJECT / "outputs/candidate-map.png"
    fig.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(fig)
    audit = {
        "question": "候補面はどこにあり、単純順位と主条件でどう違うか",
        "sources": [str(summary_path.relative_to(PROJECT)), str(cells_path.relative_to(PROJECT))],
        "ctrees_revision": summary["inputs"]["ctrees"]["revision"],
        "forty_revision": summary["inputs"]["forty"]["revision"],
        "counts": {key: len(value) for key, value in categories.items()},
        "background_n": len(background),
        "crs": "EPSG:4326 coordinates shown; no area measured on this figure",
        "unit": "one CTrees aggregation cell center per point",
        "font": font,
        "warning": "model-estimate screening; not observed forest loss",
    }
    output.with_suffix(".json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
