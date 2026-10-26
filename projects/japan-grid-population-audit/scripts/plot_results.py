"""Plot existing per-prefecture ranking results; does not recalculate analysis.

uv run --no-project --with matplotlib python3 \
  projects/japan-grid-population-audit/scripts/plot_results.py
"""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPOSITORY = PROJECT.parents[1]
SOURCE = PROJECT / "outputs" / "full-summary.json"
FIGURE = PROJECT / "outputs" / "prefecture-recall.png"


def paired_prefecture_points(rows: list[dict]) -> list[tuple[str, int, float, float]]:
    required = {"prefecture", "meshes", "ghsl_center_recall10", "ghsl_area_recall10"}
    points = []
    for row in rows:
        if not required.issubset(row):
            raise ValueError("missing paired prefecture result")
        points.append(
            (
                row["prefecture"],
                row["meshes"],
                row["ghsl_center_recall10"],
                row["ghsl_area_recall10"],
            )
        )
    return points


def run() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(
        0, str(REPOSITORY / ".agents" / "skills" / "analysis-visualize" / "scripts")
    )
    from cjk_font import use_cjk_font

    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    points = paired_prefecture_points(data["prefecture_summary"])
    if len(points) != 46 or len({row[0] for row in points}) != 46:
        raise ValueError("prefecture summary has an unexpected scope")
    font = use_cjk_font(
        "都道府県別 人口上位10%の一致率 中心点割当 面積按分 東京 神奈川 大阪 対角線 低い 高い"
    )
    fig, ax = plt.subplots(figsize=(7.2, 6.8), layout="constrained")
    ax.scatter(
        [p[2] for p in points],
        [p[3] for p in points],
        s=34,
        alpha=0.82,
        color="#126782",
    )
    ax.plot([0, 1], [0, 1], linestyle="--", color="#777777", linewidth=1)
    for code, label, offset in (
        ("13", "東京", (6, 6)),
        ("14", "神奈川", (6, -16)),
        ("27", "大阪", (6, 6)),
    ):
        p = next(p for p in points if p[0] == code)
        ax.annotate(
            label, (p[2], p[3]), xytext=offset, textcoords="offset points", fontsize=9
        )
    ax.set(
        xlim=(0, 1),
        ylim=(0, 1),
        xlabel="中心点割当の一致率",
        ylabel="面積按分の一致率",
        title="都道府県別・人口上位10%の候補一致率",
    )
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.2)
    fig.savefig(FIGURE, dpi=180)
    plt.close(fig)
    metadata = {
        "question": "都道府県内の人口上位10%候補の一致率は面積按分と中心点割当でどう違うか",
        "source": str(SOURCE.relative_to(PROJECT)),
        "source_versions": data["source_versions"],
        "units": "46 prefectures with at least 20 eligible meshes; Okinawa absent from fixed GHSL tiles",
        "n": len(points),
        "x": "GHSL centroid-assignment recall at prefecture-local top 10%",
        "y": "GHSL equal-area allocation recall at prefecture-local top 10%",
        "axis_range": [0, 1],
        "reference_line": "equal recall",
        "intervals": "none",
        "font": font,
    }
    FIGURE.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(FIGURE)


if __name__ == "__main__":
    run()
