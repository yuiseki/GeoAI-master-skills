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
    title = "街の型は、はっきり分かれた塊になっていたか"
    xlabel = "シルエット係数 (理論上 -1〜1)"
    font = use_cjk_font(title + xlabel + "対象地域台東区東京23区観測された範囲")

    fig, ax = plt.subplots(figsize=(9, 4.8))
    colors = ["#0072B2", "#D55E00"]
    for y, (row, color) in enumerate(zip(rows, colors, strict=True)):
        lower, upper = float(row["min_silhouette"]), float(row["max_silhouette"])
        ax.hlines(y, lower, upper, color=color, linewidth=5)
        ax.scatter([lower, upper], [y, y], color=color, s=70, zorder=3)
        ax.text(
            upper + 0.035,
            y,
            f"{lower:.2f}-{upper:.2f} (n={int(row['n']):,})",
            va="center",
        )
    ax.axvline(0, color="#666666", linewidth=1)
    ax.set_yticks(range(len(rows)), [row["area"] for row in rows])
    ax.set_xlim(-1, 1)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("対象地域")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUTPUT / "silhouette-ranges.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    metadata = {
        "question": title,
        "kind": "distribution_summary",
        "source_values": "outputs/source-values.csv",
        "source": "study-geoai-algo-py/case-studies/004-town-types/README.md",
        "source_commit": SOURCE_COMMIT,
        "source_rows": len(rows),
        "data_version": "実験結果 2026-09-29。入力データの版は元事例要約では未確認",
        "n": {"taito_neighborhoods": 108, "tokyo23_neighborhoods": 3150},
        "interval_meaning": (
            "横線は試した k にわたるシルエット係数の最小と最大。推定区間ではない"
        ),
        "axes": {"x": "シルエット係数", "y": "対象地域"},
        "axis_limits": {"x": [-1, 1]},
        "font": font,
        "generated_on": "2026-10-23",
        "limitation": (
            "型の場所と中身は表せないため、元コードの clusters、PCA、DPMM の"
            "地図の方が適している"
        ),
    }
    (OUTPUT / "silhouette-ranges.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
