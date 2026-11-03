"""The vector inputs, cut to the box, as GeoJSON in longitude and latitude under artifacts/.../raw/vectors/.

uvx --with duckdb==1.5.5 --with pyproj python scripts/01_fetch_vectors.py

- rec_2019.geojson: the 2019 polygons of the flood records (tokyo-flood-record-jp, flood_area.parquet), all columns
  but the geometry kept as properties. The source is JGD2000 (EPSG:4612); its difference from WGS 84 is ignored.
- a31a_max.geojson: the A31a 想定最大規模 polygons (ksj-a31a-flood-greater-tokyo, categories/maximum.parquet) that
  intersect the box, with river name, manager and depth class. JGD2011 (EPSG:6668).
- tokyo.geojson: the municipalities of Tokyo from N03 (2026-01-01) that intersect the box.
- tama.geojson: the OSM ways waterway=river, name=多摩川 that intersect the box, from overpass.yuiseki.net
  (data frozen at 2025-09-14; the public OSM servers are not used).
raw/vectors/MANIFEST.json lists each file with its source, the rows and the sha256.
"""
import json
import urllib.parse
import zipfile

import duckdb

from common import A31A_MAX, BOX_LONLAT, FLOOD_RECORD, N03_TOKYO, OVERPASS, RAW, get, sha


def main():
    d = RAW / "vectors"
    d.mkdir(parents=True, exist_ok=True)
    w, s, e, n = BOX_LONLAT
    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial")
    env = f"ST_MakeEnvelope({w}, {s}, {e}, {n})"
    man = []

    def write(name, rows, source):
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": json.loads(g), "properties": p} for g, p in rows]}
        (d / name).write_text(json.dumps(fc, ensure_ascii=False) + "\n", encoding="utf-8")
        man.append({"path": f"vectors/{name}", "source": source, "rows": len(rows), "sha256": sha(d / name)})
        print(name, len(rows))

    cols = [r[0] for r in c.sql(f"describe from '{FLOOD_RECORD}'").fetchall() if r[0] != "geometry"]
    q = c.sql(f"select ST_AsGeoJSON(geometry::GEOMETRY), {', '.join(cols)} from '{FLOOD_RECORD}' where year = 2019")
    write("rec_2019.geojson", [(r[0], {k: (str(v) if v is not None and not isinstance(v, (int, float, str)) else v)
                                       for k, v in zip(cols, r[1:])}) for r in q.fetchall()],
          f"{FLOOD_RECORD} (HF yuiseki/tokyo-flood-record-jp, local tree commit 4c88d8d)")

    q = c.sql(f"""select ST_AsGeoJSON(geometry::GEOMETRY), river_name, manager, class_code, id from '{A31A_MAX}'
                  where ST_Intersects(geometry::GEOMETRY, {env})""")
    write("a31a_max.geojson", [(r[0], {"river_name": r[1], "manager": r[2], "class_code": r[3], "id": r[4]})
                               for r in q.fetchall()], f"{A31A_MAX} (HF yuiseki/ksj-a31a-flood-greater-tokyo, FY2025)")

    with zipfile.ZipFile(N03_TOKYO) as z:
        gj = json.loads(z.read("N03-20260101_13.geojson"))
    tmp = RAW / "vectors" / "_n03.geojson"
    tmp.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    q = c.sql(f"""select ST_AsGeoJSON(geom), N03_004, N03_007 from ST_Read('{tmp}')
                  where ST_Intersects(geom, {env})""")
    write("tokyo.geojson", [(r[0], {"N03_004": r[1], "N03_007": r[2]}) for r in q.fetchall()],
          f"{N03_TOKYO.name} (国土数値情報 行政区域 N03, 2026-01-01)")
    tmp.unlink()

    ql = f'[out:json][timeout:120];way["waterway"="river"]["name"="多摩川"]({s},{w},{n},{e});out geom meta;'
    r = json.loads(get(OVERPASS, data=urllib.parse.urlencode({"data": ql}).encode(),
                       headers={"User-Agent": "GeoAI-master-skills/hagibis-tokyo-sar-flood-record",
                                "content-type": "application/x-www-form-urlencoded"}))
    rows = [(json.dumps({"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in el["geometry"]]}),
             {"osm_way": el["id"], "version": el["version"], "timestamp": el["timestamp"], **el["tags"]})
            for el in r["elements"]]
    write("tama.geojson", rows, f"{OVERPASS} (osm_base {r['osm3s'].get('timestamp_osm_base')}), "
                                "© OpenStreetMap contributors, ODbL 1.0")
    (d / "MANIFEST.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
