"""Count the 1 km cells by the size of the estimated AGB change, from outputs/cell_metrics.csv.

drop is AGB 2010 minus AGB 2025 (Mg/ha), so a positive drop is a fall. The report quotes these three counts; they are
written here instead of being counted in the report.

uv run python scripts/summarize_drop.py
"""

import csv
import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "outputs"
STEP = 2.0  # Mg/ha


def classify(drops, step=STEP):
    return {
        "fall_at_least_2": sum(d >= step for d in drops),
        "rise_more_than_2": sum(d < -step for d in drops),
        "between": sum(-step <= d < step for d in drops),
        "cells": len(drops),
    }


def main():
    with (OUTPUT / "cell_metrics.csv").open(encoding="utf-8") as f:
        drops = [float(row["drop"]) for row in csv.DictReader(f)]
    record = {"input": "outputs/cell_metrics.csv", "step_mg_ha": STEP, **classify(drops)}
    (OUTPUT / "drop-classes.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
