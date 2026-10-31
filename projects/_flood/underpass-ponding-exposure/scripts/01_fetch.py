"""Fetch the small inputs at pinned revisions into artifacts/_flood/underpass-ponding-exposure/raw/.

uvx --from 'duckdb>=1.5.5' python scripts/01_fetch.py

The OSM line table (1.85 GB) is downloaded separately to raw/planet_osm_line.parquet (see README) and cut by
03_roads.py; the elevation tiles are fetched by 02_dem.py.
"""
from pathlib import Path

import duckdb

ART = Path(__file__).resolve().parents[4] / "artifacts/_flood/underpass-ponding-exposure/raw"
ART.mkdir(parents=True, exist_ok=True)

FR = "hf://datasets/yuiseki/tokyo-flood-record-jp@354b0d9f8030347192eaa387500f60da76c07e1a/parquet"
KS = "hf://datasets/yuiseki/mlit-kansui-flood-prone-points-pdf-jp-2026-09@34e24d0c94dbeec34a45dba934675ec1a1cf0a97/parquet"
RAIN = "hf://datasets/yuiseki/jma-rain-tokyo@4391f7698523f5fd8f7c485a407a20f1545a6fc9/parquet"
SRC = {
    "underpass": "hf://datasets/yuiseki/mlit-underpass@4d00072aa88696cfa7026c4cef7d600bc96f9f13/parquet/national.parquet",
    "kansui_points": "hf://datasets/yuiseki/mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f6a3278a9956044094acd852a73c5283f2/parquet/kansui_points.parquet",
    "kansui_pdf_records": f"{KS}/pdf_records.parquet",
    "kansui_point_pdf": f"{KS}/point_pdf.parquet",
    "flood_record_area": f"{FR}/flood_area.parquet",
    "flood_record_point": f"{FR}/flood_point.parquet",
    "rain_daily": f"{RAIN}/daily.parquet",
    "rain_stations": f"{RAIN}/stations.parquet",
}


def main():
    con = duckdb.connect()
    con.execute("load spatial")
    for name, url in SRC.items():
        out = ART / f"{name}.parquet"
        if not out.exists():
            con.execute(f"copy (select * from '{url}') to '{out}' (format parquet)")
        print(name, con.execute(f"select count(*) from '{out}'").fetchone()[0])


if __name__ == "__main__":
    main()
