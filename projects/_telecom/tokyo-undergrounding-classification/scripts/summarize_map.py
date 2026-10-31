"""Count the 250 m cells of the Taito map from its provenance (outputs/taito-underground-share.json).

The report quotes how many cells were drawn and how many were left as NoData; they are written here instead of
being added up in the report.

uv run python scripts/summarize_map.py
"""

import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "outputs"


def summarize(meta):
    drawn = sum(meta["units_per_class"])
    return {"cells_drawn": drawn, "cells_nodata": meta["nodata_units"], "cells_total": drawn + meta["nodata_units"]}


def main():
    meta = json.loads((OUTPUT / "taito-underground-share.json").read_text(encoding="utf-8"))
    record = {"input": "outputs/taito-underground-share.json", **summarize(meta)}
    (OUTPUT / "map-summary.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
