"""Read one Overture type for a lon/lat box and write it to Parquet: only the files whose STAC item box overlaps,
filtered by the row bbox.

    transportation/segment   lines with subtype and class (road, rail, water)
    base/water               water lines and polygons with subtype and class (river, stream, canal, lake, ...)
    buildings/building       one point per building (the centroid) with the first source dataset

Usage:
    uvx --from 'duckdb>=1.5.5' python fetch_overture.py THEME TYPE MINLON MINLAT MAXLON MAXLAT OUT.parquet [--release 2026-09-23.1]
"""

import argparse
import json
import time
import urllib.request

STAC = "https://stac.overturemaps.org/{rel}/{theme}/{type}/collection.json"


def overlaps(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def item_urls(rel, theme, typ, box):
    col = json.load(urllib.request.urlopen(STAC.format(rel=rel, theme=theme, type=typ), timeout=60))
    base = STAC.format(rel=rel, theme=theme, type=typ).rsplit("/", 1)[0]
    urls = []
    for link in col["links"]:
        if link.get("rel") != "item":
            continue
        href = link["href"] if link["href"].startswith("http") else f"{base}/{link['href'].lstrip('./')}"
        it = json.load(urllib.request.urlopen(href, timeout=60))
        if overlaps(it["bbox"], box):
            s3 = [a["href"] for a in it["assets"].values() if a["href"].startswith("s3://")]
            urls += s3 or [a["href"] for a in it["assets"].values()]
    return urls


def main():
    import duckdb

    ap = argparse.ArgumentParser()
    ap.add_argument("theme")
    ap.add_argument("type")
    ap.add_argument("box", type=float, nargs=4)
    ap.add_argument("out")
    ap.add_argument("--release", default="2026-09-23.1")
    a = ap.parse_args()
    t0 = time.time()
    urls = item_urls(a.release, a.theme, a.type, a.box)
    print(f"{a.theme}/{a.type}: {len(urls)} files overlap the box ({time.time() - t0:.0f} s)")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region = 'us-west-2';")
    x0, y0, x1, y1 = a.box
    where = f"bbox.xmin <= {x1} AND bbox.xmax >= {x0} AND bbox.ymin <= {y1} AND bbox.ymax >= {y0}"
    files = "[" + ", ".join(f"'{u}'" for u in urls) + "]"
    if a.type == "building":
        sel = "ST_X(ST_Centroid(geometry)) AS lon, ST_Y(ST_Centroid(geometry)) AS lat, sources[1].dataset AS source"
    else:
        sel = "subtype, class, ST_AsWKB(geometry) AS wkb"
    con.execute(f"COPY (SELECT {sel} FROM read_parquet({files}) WHERE {where}) TO '{a.out}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT count(*) FROM '{a.out}'").fetchone()[0]
    print(f"wrote {a.out}: {n} rows in {time.time() - t0:.0f} s")
    group = "source" if a.type == "building" else "subtype, class"
    print(con.execute(f"SELECT {group}, count(*) FROM '{a.out}' GROUP BY ALL ORDER BY 2 DESC LIMIT 12").fetchall())


if __name__ == "__main__":
    main()
