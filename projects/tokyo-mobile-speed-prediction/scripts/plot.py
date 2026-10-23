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
    models = [row for row in rows if row["kind"] == "model"]
    baseline = next(row for row in rows if row["kind"] == "baseline")
    labels = [row["label"] for row in models]
    values = [float(row["estimate"]) for row in models]
    lower, upper = float(baseline["lower"]), float(baseline["upper"])

    title = "街の特徴を使うモデルは、前四半期の基準を超えたか"
    ylabel = "測定回数で重み付けした R²"
    font = use_cjk_font(
        title + ylabel + "モデルまたは基準" + "".join(labels) + "縮めた前四半期"
    )

    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.axhspan(
        lower, upper, color="#999999", alpha=0.22, label="縮めた前四半期: 0.12-0.16"
    )
    ax.axhline(0, color="#555555", linewidth=1)
    ax.scatter(range(len(models)), values, color="#0072B2", s=70, zorder=3)
    for x, value in enumerate(values):
        ax.annotate(
            f"{value:.3f}",
            (x, value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
        )
    ax.set_xticks(range(len(models)), labels, rotation=18, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_ylim(-0.03, 0.20)
    ax.set_title(title)
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    fig.text(
        0.99,
        0.01,
        "モデル n=2,246タイル / 前四半期基準 n=1,745タイル",
        ha="right",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUTPUT / "model-r2.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    metadata = {
        "question": title,
        "kind": "comparison",
        "source_values": "outputs/source-values.csv",
        "source": "study-geoai-algo-py/case-studies/001-mobile-speed/README.md",
        "source_commit": SOURCE_COMMIT,
        "source_rows": len(rows),
        "data_version": "実験結果 2026-09-29。各入力データの版は元事例を参照",
        "n": {"models": 2246, "shrunken_previous_quarter": 1745},
        "interval_meaning": (
            "灰色は元事例に記録された縮めた前四半期の R² の範囲。推定区間ではない"
        ),
        "axes": {"x": "モデルまたは基準", "y": "測定回数で重み付けした R²"},
        "axis_limits": {"y": [-0.03, 0.20]},
        "font": font,
        "generated_on": "2026-10-23",
    }
    (OUTPUT / "model-r2.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
