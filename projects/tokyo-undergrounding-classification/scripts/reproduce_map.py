"""Map the original Taito 250 m undergrounding shares with analysis-visualize."""

import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
SOURCE = ROOT / "projects/tokyo-town-types/tmp/source"
COMMIT = "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
DRAW = ROOT / ".agents/skills/analysis-visualize/scripts/classify_map.py"
MIN_SCENES = 30


def aggregate_cells(cells, labels):
    if len(cells) != len(labels):
        raise ValueError("row count mismatch between cell IDs and labels")
    counts = defaultdict(lambda: [0, 0])
    for cell, label in zip(cells, labels, strict=True):
        if label not in (0, 1):
            raise ValueError("labels must be binary")
        counts[int(cell)][0] += 1
        counts[int(cell)][1] += int(label)
    return [
        (cell, n, positive / n if n >= MIN_SCENES else None)
        for cell, (n, positive) in sorted(counts.items())
    ]


def main():
    revision = subprocess.check_output(["git", "-C", SOURCE, "rev-parse", "HEAD"], text=True).strip()
    if revision != COMMIT:
        raise RuntimeError(f"expected source commit {COMMIT}, got {revision}")
    sys.path.insert(0, str(SOURCE / "src"))
    from study_geoai import michiyomi, tasks
    from study_geoai.db import connect

    con = connect()
    task = tasks.undergrounded(con, "taito")
    rows = aggregate_cells(task.groups["cell_250m"], task.y)
    eligible = sum(value is not None for _, _, value in rows)
    if len(task.y) != 32593 or eligible == 0:
        raise RuntimeError(f"source rows changed: {len(task.y)} scenes; {eligible} eligible cells")
    con.sql("create temp table map_rows (unit_id bigint, n_scenes integer, underground_share double, wkt varchar)")
    values = []
    for cell, n, share in rows:
        w, s, e, north = michiyomi.cell_bounds(cell)
        values.append((cell, n, share, f"POLYGON(({w} {s},{e} {s},{e} {north},{w} {north},{w} {s}))"))
    con.executemany("insert into map_rows values (?, ?, ?, ?)", values)
    temp = PROJECT / "tmp"
    temp.mkdir(exist_ok=True)
    table = temp / "taito-underground-share.parquet"
    con.sql(f"copy (select unit_id, n_scenes, underground_share, st_geomfromtext(wkt) as geometry "
            f"from map_rows order by unit_id) to '{table}' (format parquet)")
    for method, other in (("equal", "quantile"), ("quantile", "equal")):
        name = "taito-underground-share" if method == "equal" else "taito-underground-share-quantile"
        output = PROJECT / "outputs" / f"{name}.png"
        subprocess.run([
            sys.executable, str(DRAW), str(table), "unit_id", "underground_share",
            "--kind", "rate", "--unit", "割合 (0–1)", "--method", method, "--classes", "5",
            "--compare", other, "--crs", "OGC:CRS84",
            "--source", f"michiyomi e4966cdceff6; study-geoai {COMMIT[:8]}",
            "--no-labels", "--png", str(output),
        ], check=True)
    print(f"{len(task.y)} scenes; {len(rows)} cells; {eligible} cells with >= {MIN_SCENES} scenes")


if __name__ == "__main__":
    main()
