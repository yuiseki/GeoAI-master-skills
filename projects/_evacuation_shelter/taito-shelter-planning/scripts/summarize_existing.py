"""Count the existing designated emergency evacuation sites and their capacity from outputs/existing-shelters.csv.

The report quotes these totals; they are written here instead of being added up in the report.

uv run python scripts/summarize_existing.py
"""

import csv
import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "outputs"


def summarize(rows):
    open_rows = [row for row in rows if row["arakawa_open"] == "True"]
    return {
        "existing_shelters_count": len(rows),
        "existing_shelters_capacity_total": sum(int(row["capacity"]) for row in rows),
        "arakawa_open_shelters_count": len(open_rows),
        "arakawa_open_shelters_capacity": sum(int(row["capacity"]) for row in open_rows),
    }


def main():
    with (OUTPUT / "existing-shelters.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    (OUTPUT / "existing-shelters-summary.json").write_text(
        json.dumps({"input": "outputs/existing-shelters.csv", **summarize(rows)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
