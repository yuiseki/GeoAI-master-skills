"""Extract the 23-ward accidents of 2019-2025 with the columns the analysis needs.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' python -u scripts/01_extract.py

Reads the honhyo of the 7 pinned yearly files of yuiseki/npa-traffic-accidents. Keeps 都道府県コード 30,
市区町村コード 101-123, a position, and an occurrence year 2019-2025. Writes
artifacts/_traffic_accident/tokyo23-fatal-share-road-anomaly/accidents.parquet and outputs/extract.json (row counts
at each step).
"""
import json
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ART = HERE.parents[3] / "artifacts/_traffic_accident/tokyo23-fatal-share-road-anomaly"
NPA_REV = "389500aae5cec45f1311163f70db6a5f05867838"
SRC = f"hf://datasets/yuiseki/npa-traffic-accidents@{NPA_REV}/parquet/*/honhyo.parquet"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"
FAR_M = 1000  # a point this far outside the 23 wards is not a border-road position error (D3)


def main():
    ART.mkdir(parents=True, exist_ok=True)
    c = duckdb.connect()
    c.execute(f"""create table t as select regexp_extract(filename, 'parquet/(\\d{{4}})/', 1) file_year,
        "都道府県コード" pref, "警察署等コード" station, "本票番号" no, "市区町村コード" city,
        cast("発生日時　　年" as int) occ_year, cast("死者数" as int) died, cast("負傷者数" as int) injured,
        "事故内容" kind, "道路形状" shape, "車道幅員" width, "中央分離帯施設等" median, "歩車道区分" sidewalk,
        "信号機" signal, "道路線形" alignment, "路線コード" route, "事故類型" accident_type,
        "当事者種別（当事者A）" party_a, "当事者種別（当事者B）" party_b, latitude, longitude
      from read_parquet('{SRC}', union_by_name = true, filename = true)
      where "都道府県コード" = '30'""")
    n = {}
    n["tokyo_rows"] = c.execute("select count(*) from t").fetchone()[0]
    c.execute("delete from t where city not between '101' and '123'")
    n["ward_rows"] = c.execute("select count(*) from t").fetchone()[0]
    n["ward_no_position"] = c.execute("select count(*) from t where latitude is null").fetchone()[0]
    c.execute("delete from t where latitude is null")
    n["ward_year_outside"] = c.execute("select count(*) from t where occ_year not between 2019 and 2025").fetchone()[0]
    c.execute("delete from t where occ_year not between 2019 and 2025")
    c.execute("load spatial")
    c.execute("set geometry_always_xy = true")
    c.execute(f"""create table w as select st_transform(st_union_agg(geometry), 'EPSG:4326', 'EPSG:6677') g
                  from '{ADMIN}' where code5 between '13101' and '13123'""")
    c.execute("""create table far as select station, no, file_year, latitude, longitude, died, st_distance(
                  st_transform(st_point(longitude, latitude), 'EPSG:4326', 'EPSG:6677'), w.g) dist_m from t, w""")
    n["ward_outside_m"] = c.execute("select count(*) from far where dist_m > 0").fetchone()[0]
    n[f"ward_outside_far_{FAR_M}m"] = c.execute(f"select count(*) from far where dist_m > {FAR_M}").fetchone()[0]
    n["far_points"] = [dict(zip(("file_year", "station", "no", "lat", "lon", "died", "dist_m"), r)) for r in c.execute(
        f"select file_year, station, no, latitude, longitude, died, round(dist_m) from far where dist_m > {FAR_M}").fetchall()]
    c.execute(f"""delete from t where (file_year, station, no) in
                  (select (file_year, station, no) from far where dist_m > {FAR_M})""")
    n["kept"] = c.execute("select count(*) from t").fetchone()[0]
    n["kept_fatal"] = c.execute("select count(*) from t where died > 0").fetchone()[0]
    n["kind_fatal_mismatch"] = c.execute("select count(*) from t where (died > 0) <> (kind = '1')").fetchone()[0]
    n["dup_keys"] = c.execute("select count(*) - count(distinct (file_year, station, no)) from t").fetchone()[0]
    c.execute(f"copy t to '{ART / 'accidents.parquet'}' (format parquet)")
    n["npa_revision"] = NPA_REV
    (HERE.parent / "outputs" / "extract.json").write_text(json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(n, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
