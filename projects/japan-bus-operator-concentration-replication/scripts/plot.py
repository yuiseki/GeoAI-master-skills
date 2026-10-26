"""Draw the independently reproduced municipality choropleth.

uv run --no-project --with duckdb --with numpy --with shapely --with matplotlib \
  python3 projects/japan-bus-operator-concentration-replication/scripts/plot.py
"""

import csv
import subprocess
import sys
from pathlib import Path

from analysis import ARTIFACTS, PROJECT, url

ROOT = PROJECT.parents[1]
DRAW = ROOT / ".agents/skills/analysis-visualize/scripts/classify_map.py"


def map_share(row):
    denominator = int(row["stop_older_population"])
    numerator = int(row["single_older_population"])
    if denominator < 0 or numerator < 0 or numerator > denominator:
        raise ValueError("invalid population share")
    return 100 * numerator / denominator if denominator else None


def main():
    import duckdb

    summary_path = PROJECT / "outputs/municipalities.csv"
    with summary_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1740 or len({r["code5"] for r in rows}) != len(rows):
        raise ValueError("municipality summary is incomplete or duplicated")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial")
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute("CREATE TEMP TABLE metric (code5 VARCHAR, share_pct DOUBLE)")
    con.executemany("INSERT INTO metric VALUES (?, ?)", [(r["code5"], map_share(r)) for r in rows])
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    table = ARTIFACTS / "map_units.parquet"
    con.execute(
        f"COPY (SELECT m.code5, x.share_pct, m.geometry "
        f"FROM read_parquet(?) m LEFT JOIN metric x ON m.code5=x.code5 "
        f"WHERE m.ward IS NULL AND m.geometry IS NOT NULL ORDER BY m.code5) "
        f"TO '{table}' (FORMAT PARQUET)",
        [url("admin")],
    )
    counts = con.execute("SELECT count(*), count(share_pct) FROM read_parquet(?)", [str(table)]).fetchone()
    if counts[0] != 1741 or counts[1] != 1666:
        raise ValueError(f"unexpected mapped values and NoData: {counts}")
    image = PROJECT / "outputs/municipality-share.png"
    subprocess.run([
        sys.executable, str(DRAW), str(table), "code5", "share_pct",
        "--kind", "rate", "--unit", "%（停留所圏の65歳以上人口）",
        "--method", "fixed", "--thresholds", "20", "40", "60", "80",
        "--compare", "quantile", "--classes", "5", "--palette", "YlOrRd",
        "--crs", "EPSG:4612", "--source", "P11 2022・国勢調査2020・行政界2020／固定版",
        "--no-labels", "--png", str(image),
    ], check=True)
    print(f"map source: {counts[1]} values, {counts[0]-counts[1]} NoData; {image}")


if __name__ == "__main__":
    main()
