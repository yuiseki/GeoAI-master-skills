import csv
import importlib.util
import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
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
    title = "評価地点を離すと、無電柱化分類の AUC は下がるか"
    all_text = (
        title + "評価の分け方AUC台東区東京23区" + "".join(row["split"] for row in rows)
    )
    font = use_cjk_font(all_text)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True)
    for ax, area, color in zip(
        axes, ["台東区", "東京23区"], ["#0072B2", "#D55E00"], strict=True
    ):
        part = sorted(
            (row for row in rows if row["area"] == area),
            key=lambda row: int(row["order"]),
        )
        labels = [row["split"] for row in part]
        values = [float(row["auc"]) for row in part]
        ax.plot(range(len(part)), values, marker="o", color=color, linewidth=2)
        for x, value in enumerate(values):
            ax.annotate(
                f"{value:.3f}",
                (x, value),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
            )
        ax.set_xticks(range(len(part)), labels, rotation=22, ha="right")
        ax.set_ylim(0.5, 1.0)
        ax.set_title(f"{area} (n={int(part[0]['n']):,}シーン)")
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("AUC")
    fig.supxlabel("評価の分け方")
    fig.suptitle(title)
    fig.tight_layout()
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUTPUT / "auc-by-split.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    metadata = {
        "question": title,
        "kind": "comparison",
        "source_values": "outputs/source-values.csv",
        "source": "study-geoai-algo-py/case-studies/003-undergrounding/README.md",
        "source_commit": SOURCE_COMMIT,
        "source_rows": len(rows),
        "data_version": "実験結果 2026-09-29。みちよみの版は元事例要約では未確認",
        "n": {"taito_scenes": 32593, "tokyo23_scenes": 988619},
        "interval_meaning": "区間は描いていない。線は分割条件を順に結ぶ案内線",
        "axes": {"x": "評価の分け方", "y": "AUC"},
        "axis_limits": {"y": [0.5, 1.0]},
        "font": font,
        "generated_on": "2026-10-23",
    }
    (OUTPUT / "auc-by-split.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
