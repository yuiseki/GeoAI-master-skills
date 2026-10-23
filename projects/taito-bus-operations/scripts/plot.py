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
    vehicles = [row for row in rows if row["kind"] == "vehicle"]
    drivers = next(row for row in rows if row["kind"] == "driver")
    title = "めぐりん171便に必要な車両と乗務員は何人か"
    font = use_cjk_font(title + "折り返し時間必要車両数必要乗務員数最適値の範囲分台人")

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))
    layovers = [0, 3]
    counts = [int(row["value"]) for row in vehicles]
    axes[0].plot(
        layovers, counts, marker="o", markersize=8, color="#0072B2", linewidth=2
    )
    for x, value in zip(layovers, counts, strict=True):
        axes[0].annotate(
            f"{value}台",
            (x, value),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
        )
    axes[0].set_xlabel("折り返し時間 (分)")
    axes[0].set_ylabel("必要車両数 (台)")
    axes[0].set_xlim(-0.25, 3.25)
    axes[0].set_ylim(0, 20)
    axes[0].set_xticks(layovers)
    axes[0].set_title("折り返し時間で車両数が変わる")
    axes[0].grid(alpha=0.25)

    lower, upper = int(drivers["lower"]), int(drivers["upper"])
    axes[1].hlines(0, lower, upper, color="#D55E00", linewidth=6)
    axes[1].scatter([lower, upper], [0, 0], color="#D55E00", s=90, zorder=3)
    axes[1].annotate(
        f"下限 {lower}人",
        (lower, 0),
        xytext=(0, 12),
        textcoords="offset points",
        ha="center",
    )
    axes[1].annotate(
        f"実行可能 {upper}人",
        (upper, 0),
        xytext=(0, -22),
        textcoords="offset points",
        ha="center",
    )
    axes[1].set_xlim(0, 40)
    axes[1].set_ylim(-0.7, 0.7)
    axes[1].set_yticks([])
    axes[1].set_xlabel("必要乗務員数 (人)")
    axes[1].set_title("最適値は33〜35人")
    axes[1].grid(axis="x", alpha=0.25)
    fig.suptitle(title)
    fig.tight_layout()
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
        fig.savefig(OUTPUT / "resource-bounds.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    metadata = {
        "question": title,
        "kind": "comparison_and_bounds",
        "source_values": "outputs/source-values.csv",
        "source": "study-geoai-algo-py/case-studies/005-bus-operations/README.md",
        "source_commit": SOURCE_COMMIT,
        "source_rows": len(rows),
        "data_version": "実験結果 2026-09-29。GTFS-JP の版は元事例要約では未確認",
        "n": {"weekday_trips": 171},
        "interval_meaning": (
            "33人は不可能と示せた下限、35人は制限時間内に見つかった"
            "実行可能解。統計的区間ではない"
        ),
        "axes": {
            "left": "折り返し時間 (分) と必要車両数 (台)",
            "right": "必要乗務員数 (人)",
        },
        "axis_limits": {"vehicles_y": [0, 20], "drivers_x": [0, 40]},
        "font": font,
        "generated_on": "2026-10-23",
        "limitation": (
            "便ごとのつながりと勤務の実行可能性は、元コードの blocks と duties の"
            "ガント図の方が詳しい"
        ),
    }
    (OUTPUT / "resource-bounds.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
