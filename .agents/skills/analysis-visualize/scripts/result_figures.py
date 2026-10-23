"""Render verified Pareto fronts or interval schedules from analysis output JSON.

Usage: python result_figures.py input.json output.png
See references/result-figures.md for the two input schemas.
"""

import argparse
import itertools
import json
import math
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cjk_font import use_cjk_font


def finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite coordinate")
    return number


def pareto(data, ax):
    points = data["points"]
    if not points:
        raise ValueError("empty Pareto points")
    if data["x_direction"] not in ("min", "max") or data["y_direction"] not in ("min", "max"):
        raise ValueError("directions must be min or max")
    rows = []
    seen = set()
    for point in points:
        x, y = finite(point["x"]), finite(point["y"])
        if (x, y) in seen:
            raise ValueError("duplicate Pareto coordinate")
        seen.add((x, y))
        methods = point["methods"]
        if not methods or len(methods) != len(set(methods)):
            raise ValueError("each point needs distinct method names")
        rows.append((x, y, methods, point.get("front", True)))
    front = [row for row in rows if row[3]]
    if not front:
        raise ValueError("no front points")
    sx = 1 if data["x_direction"] == "max" else -1
    sy = 1 if data["y_direction"] == "max" else -1
    for x, y, _, _ in front:
        if any(
            sx * xx >= sx * x and sy * yy >= sy * y
            and (xx != x or yy != y)
            for xx, yy, _, _ in front
        ):
            raise ValueError("dominated point on Pareto front")
    front.sort(key=lambda row: row[0])
    ax.step([r[0] for r in front], [r[1] for r in front], where="post", color="#777777", linewidth=1)
    method_counts = Counter(method for _, _, methods, _ in rows for method in methods)
    base_methods = [method for method in method_counts if all(method in row[2] for row in front)]
    base_method = base_methods[0] if base_methods else None
    ax.scatter([r[0] for r in front], [r[1] for r in front], s=42, color="#3069a2",
               label=f"パレート解: {base_method} ({len(front)})" if base_method else "パレート解")
    for index, method in enumerate(sorted(method_counts)):
        if method == base_method:
            continue
        selected = [r for r in rows if method in r[2]]
        ax.scatter(
            [r[0] for r in selected], [r[1] for r in selected],
            s=100 + index * 35, facecolors="none", edgecolors=["#c54131", "#7142a5", "#148466"][index % 3],
            linewidths=1.4, label=f"{method} ({len(selected)})",
        )
    ax.set_xlim(left=min(0, min(r[0] for r in rows)) if min(r[0] for r in rows) >= 0 else None)
    ax.set_ylim(bottom=min(0, min(r[1] for r in rows)) if min(r[1] for r in rows) >= 0 else None)
    ax.legend(frameon=False, loc="best")
    return {"n": len(rows), "front_n": len(front), "method_counts": dict(method_counts),
            "x_range": list(ax.get_xlim()), "y_range": list(ax.get_ylim())}


def schedule(data, ax):
    intervals = data["intervals"]
    if not intervals:
        raise ValueError("empty schedule")
    if data["time_unit"] != "seconds":
        raise ValueError("time_unit must be seconds")
    groups = list(dict.fromkeys(str(row["group"]) for row in intervals))
    kinds = list(dict.fromkeys(str(row["kind"]) for row in intervals))
    by_group = defaultdict(list)
    checked = []
    for row in intervals:
        start, end = finite(row["start"]), finite(row["end"])
        if start < 0 or start >= end:
            raise ValueError("interval start must precede end")
        group = str(row["group"])
        by_group[group].append((start, end))
        checked.append((group, start, end, str(row["kind"])))
    for group, spans in by_group.items():
        ordered = sorted(spans)
        if any(b[0] < a[1] for a, b in itertools.pairwise(ordered)):
            raise ValueError(f"overlap in group {group}")
    palette = ["#3069a2", "#df8d31", "#148466", "#8450a2", "#cf5363"]
    colors = {kind: palette[i % len(palette)] for i, kind in enumerate(kinds)}
    for group, start, end, kind in checked:
        ax.barh(groups.index(group), (end - start) / 3600, left=start / 3600,
                height=0.7, color=colors[kind], edgecolor="white")
    ax.set_yticks(range(len(groups)), groups)
    ax.invert_yaxis()
    low, high = min(r[1] for r in checked), max(r[2] for r in checked)
    ax.set_xlim(low / 3600 - 0.1, high / 3600 + 0.1)
    ticks = range(math.floor(low / 3600), math.ceil(high / 3600) + 1, 2)
    ax.set_xticks(list(ticks), [f"{hour:02d}:00" for hour in ticks])
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=colors[kind], label=kind) for kind in kinds], frameon=False)
    return {"n": len(checked), "groups": len(groups), "kind_counts": dict(Counter(r[3] for r in checked)),
            "time_range": [low, high]}


def draw(input_path: Path, output: Path):
    data = json.loads(input_path.read_text())
    kind = data["kind"]
    if kind not in ("pareto", "schedule"):
        raise ValueError("kind must be pareto or schedule")
    labels = [data["question"], data["x_label"], data["y_label"], data["source"], data["data_version"]]
    if kind == "pareto":
        labels += ["パレート解", *(str(m) for p in data["points"] for m in p["methods"])]
    else:
        labels += [str(p[key]) for p in data["intervals"] for key in ("group", "kind")]
    font = use_cjk_font(" ".join(labels) + "n=件時刻")
    groups = {str(row["group"]) for row in data.get("intervals", [])}
    height = max(5.2, 0.38 * len(groups) + 1.7)
    fig, ax = plt.subplots(figsize=(10.5, height))
    try:
        details = pareto(data, ax) if kind == "pareto" else schedule(data, ax)
        ax.set_xlabel(data["x_label"])
        ax.set_ylabel(data["y_label"])
        ax.set_title(data["question"], loc="left")
        ax.grid(axis="x" if kind == "schedule" else "both", alpha=0.2)
        fig.text(0.01, 0.01, f"n={details['n']} / {data['data_version']} / {data['source']}", fontsize=8)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        metadata = {"question": data["question"], "kind": kind, "source": data["source"],
                    "data_version": data["data_version"], "input": input_path.name, "font": font,
                    "x_label": data["x_label"], "y_label": data["y_label"], **details}
        output.parent.mkdir(parents=True, exist_ok=True)
        with warnings.catch_warnings():
            warnings.filterwarnings("error", message=".*Glyph.*missing from font.*")
            fig.savefig(output, dpi=170, bbox_inches="tight")
        output.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
        return metadata
    finally:
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    draw(args.input, args.output)


if __name__ == "__main__":
    main()
