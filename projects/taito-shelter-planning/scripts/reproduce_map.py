"""Map census population density in Taito's 108 towns with analysis-visualize."""

import math
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
SOURCE = ROOT / "projects/tokyo-town-types/tmp/source"
COMMIT = "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
DRAW = ROOT / ".agents/skills/analysis-visualize/scripts/classify_map.py"


def validate_towns(rows, expected_population):
    ids = [row[0] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate town ID")
    for _, population, area, density in rows:
        if not math.isfinite(area) or area <= 0:
            raise ValueError("area must be positive")
        if not math.isfinite(population) or population < 0:
            raise ValueError("population must be nonnegative")
        if not math.isclose(population / area, density, rel_tol=1e-6):
            raise ValueError("density does not match population / area")
    if not math.isclose(sum(row[1] for row in rows), expected_population, abs_tol=0.5):
        raise ValueError("population total differs from the pinned report")
    return len(rows)


def main():
    revision = subprocess.check_output(["git", "-C", SOURCE, "rev-parse", "HEAD"], text=True).strip()
    if revision != COMMIT:
        raise RuntimeError(f"expected source commit {COMMIT}, got {revision}")
    sys.path.insert(0, str(SOURCE / "src"))
    from study_geoai import aoi, features
    from study_geoai.db import connect

    con = connect()
    relation = features.small_areas(con, aoi.load("taito", con))
    relation.create_view("towns")
    rows = con.sql("select key11, population, area_km2, density from towns order by key11").fetchall()
    if validate_towns(rows, 211444) != 108:
        raise RuntimeError(f"expected 108 towns, got {len(rows)}")
    temp = PROJECT / "tmp"
    temp.mkdir(exist_ok=True)
    table = temp / "taito-population-density.parquet"
    con.sql(f"copy (select key11, density, geometry from towns order by key11) to '{table}' (format parquet)")
    output = PROJECT / "outputs/taito-population-density.png"
    subprocess.run([
        sys.executable, str(DRAW), str(table), "key11", "density",
        "--kind", "level", "--unit", "人/km²", "--method", "quantile", "--classes", "5",
        "--compare", "equal", "--crs", "OGC:CRS84",
        "--source", f"census 2020; study-geoai {COMMIT[:8]}",
        "--no-labels", "--png", str(output),
    ], check=True)
    print(f"{len(rows)} towns; total census population {sum(row[1] for row in rows):,.0f}")


if __name__ == "__main__":
    main()
