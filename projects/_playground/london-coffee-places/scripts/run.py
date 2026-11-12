"""London coffee shops from open data: the Places Insights example "top 20 coffee shop clusters in London
aggregated by H3 cell", with boroughs compared and the POI source checked against OpenStreetMap.

    uvx --python 3.12 --from 'duckdb==1.5.6' --with h3 --with s2sphere --with numpy --with scipy --with matplotlib \
        python scripts/run.py STEP

Steps, in order: fetch, extract, hotspots, boroughs, population, compare, osm, crosscheck, sensitivity, maps (or all).
Large files go to artifacts/_playground/london-coffee-places/, the small tables the report cites to outputs/.
"""

import csv
import gzip
import json
import math
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[2]
ART = ROOT / "artifacts" / "_playground" / "london-coffee-places"
OUT = HERE / "outputs"
SKILL = ROOT / ".agents" / "skills" / "poi-insights" / "scripts"
RELEASE = "2026-10-21.0"
PLACES = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/*.parquet"
DIVISIONS = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=divisions"
BBOX = (-0.52, 51.28, 0.34, 51.70)          # Greater London and a margin
KONTUR = ("https://geodata-eu-central-1-kontur-public.s3.amazonaws.com/kontur_datasets/"
          "kontur_population_GB_20231101.gpkg.gz")
LOCAL = ART / f"places_{RELEASE}_box.parquet"
OVERPASS = "https://overpass.yuiseki.net/api/interpreter"   # our own server (OSM data of 2025-09-14)


def sh(*cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def duck():
    import duckdb
    c = duckdb.connect()
    c.execute("install spatial; load spatial; install httpfs; load httpfs; set s3_region = 'us-west-2'")
    return c


def fetch():
    """Every place of the release in the box, all columns, once: the S3 scan takes minutes and the later steps
    read this copy."""
    c = duck()
    c.execute(f"""copy (select * from read_parquet('{PLACES}')
        where bbox.xmin >= {BBOX[0]} and bbox.xmax <= {BBOX[2]} and bbox.ymin >= {BBOX[1]} and bbox.ymax <= {BBOX[3]})
        to '{LOCAL}' (format parquet)""")
    n = c.execute(f"select count(*) from read_parquet('{LOCAL}')").fetchall()[0][0]
    with open(OUT / "fetch.json", "w", encoding="utf-8") as f:
        json.dump({"source": PLACES, "release": RELEASE, "bbox": BBOX, "places_in_box": n}, f, indent=1)


def extract():
    for name, cats, conf in [("coffee", ["coffee_shop"], 0.0), ("cafe_or_coffee", ["coffee_shop", "cafe"], 0.0),
                             ("coffee_conf05", ["coffee_shop"], 0.5)]:
        sh(sys.executable, SKILL / "poi_extract.py", LOCAL, ART / f"{name}.parquet", "--bbox", *BBOX,
           "--category", *cats, "--exclude-status", "permanently_closed", "--min-confidence", conf)
        shutil.copy(ART / f"{name}.parquet.audit.json", OUT / f"extract_{name}.json")
    # The closed ones too, to say how many the status filter removed and what it cannot say.
    c = duck()
    rows = c.execute(f"""select coalesce(operating_status, 'unknown'), count(*) from read_parquet('{LOCAL}')
        where bbox.xmin >= {BBOX[0]} and bbox.xmax <= {BBOX[2]} and bbox.ymin >= {BBOX[1]} and bbox.ymax <= {BBOX[3]}
          and (basic_category = 'coffee_shop' or list_contains(taxonomy.hierarchy, 'coffee_shop'))
        group by 1 order by 1""").fetchall()
    with open(OUT / "coffee_status.csv", "w", encoding="utf-8") as f:
        f.write("operating_status,places\n" + "".join(f"{s},{n}\n" for s, n in rows))
    rows = c.execute(f"""with s as (select o.id, unnest(o.sources) as src
                                    from read_parquet('{ART / 'coffee.parquet'}') p join read_parquet('{LOCAL}') o using (id)),
                         d as (select distinct id, src.dataset as dataset, src.license as license from s)
                         select dataset, license, count(*) from d group by all order by 3 desc""").fetchall()
    with open(OUT / "coffee_sources.csv", "w", encoding="utf-8") as f:
        f.write("dataset,license,places\n" + "".join(f"{d},{l},{n}\n" for d, l, n in rows))


def hotspots():
    for name, grid, res in [("h3r9", "h3", 9), ("h3r8", "h3", 8), ("h3r10", "h3", 10), ("s2l14", "s2", 14)]:
        d = ART / f"hotspots_{name}"
        sh(sys.executable, SKILL / "grid_hotspots.py", ART / "coffee.parquet", d, "--grid", grid, "--res", res,
           "--bbox", *BBOX, "--group", "brand")
        shutil.copy(d / "audit.json", OUT / f"hotspots_{name}_audit.json")
        shutil.copy(d / "clusters.csv", OUT / f"hotspots_{name}_clusters.csv")
    top20()


def top20():
    """The 20 largest clusters at H3 resolution 9, with the boroughs and brands in each."""
    import duckdb
    import h3
    cells = {}
    with open(ART / "hotspots_h3r9" / "cells.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["cluster"]:
                cells.setdefault(int(r["cluster"]), []).append(r)
    c = duckdb.connect()
    c.execute("install spatial; load spatial")
    have_b = (ART / "boroughs.parquet").exists()
    if have_b:
        c.execute(f"create table b as select region_name, geometry::geometry as g from read_parquet('{ART / 'boroughs.parquet'}')")
    with open(ART / "hotspots_h3r9" / "clusters.csv", encoding="utf-8") as f:
        clusters = list(csv.DictReader(f))
    with open(OUT / "top20_clusters.csv", "w", encoding="utf-8") as f:
        f.write("rank,cells,places,lat,lon,borough,top_brands,branded_share\n")
        for cl in clusters[:20]:
            k = int(cl["rank"])
            brands = {}
            for r in cells[k]:
                for kv in (r["groups"] or "").split(";"):
                    if kv:
                        b, n = kv.rsplit("=", 1)
                        brands[b] = brands.get(b, 0) + int(n)
            total = sum(brands.values())
            named = {b: n for b, n in brands.items() if b != "(none)"}
            top = ";".join(f"{b}={n}" for b, n in sorted(named.items(), key=lambda kv: -kv[1])[:3])
            bor = ""
            if have_b:
                q = c.execute(f"select region_name from b where st_contains(g, st_point({cl['lon']}, {cl['lat']}))").fetchall()
                bor = q[0][0] if q else ""
            f.write(f"{k},{cl['cells']},{cl['points']},{cl['lat']},{cl['lon']},{bor},\"{top}\","
                    f"{sum(named.values()) / total:.3f}\n")


# The 32 London boroughs and the City of London. In the release the county divisions in the box carry no parent
# inside the box, and three of them (Surrey, Slough, Thurrock) are outside London, so the names are listed.
LONDON_33 = ["Barking and Dagenham", "Barnet", "Bexley", "Brent", "Bromley", "Camden", "City of London", "Croydon",
             "Ealing", "Enfield", "Greenwich", "Hackney", "Hammersmith and Fulham", "Haringey", "Harrow", "Havering",
             "Hillingdon", "Hounslow", "Islington", "Kensington and Chelsea", "Kingston upon Thames", "Lambeth",
             "Lewisham", "Merton", "Newham", "Redbridge", "Richmond upon Thames", "Southwark", "Sutton",
             "Tower Hamlets", "Waltham Forest", "Wandsworth", "Westminster"]


def boroughs():
    """The 33 London boroughs (with the City): Overture divisions of subtype county, by name."""
    c = duck()
    c.execute(f"""create table d as select id, subtype, names."primary" as nm, parent_division_id, region
        from read_parquet('{DIVISIONS}/type=division/*.parquet')
        where country = 'GB' and bbox.xmin >= -0.6 and bbox.xmax <= 0.4 and bbox.ymin >= 51.2 and bbox.ymax <= 51.75""")
    london = c.execute("select id, nm, subtype from d where subtype = 'region' or nm in ('London', 'Greater London')").fetchall()
    print(london)
    rows = c.execute("""select d.id, d.nm, p.nm from d left join d p on d.parent_division_id = p.id
                        where d.subtype = 'county' order by d.nm""").fetchall()
    for r in rows:
        print(r)
    c.execute(f"""create table a as select division_id, names."primary" as nm, geometry
        from read_parquet('{DIVISIONS}/type=division_area/*.parquet')
        where country = 'GB' and subtype = 'county' and is_land
          and bbox.xmin >= -0.6 and bbox.xmax <= 0.4 and bbox.ymin >= 51.2 and bbox.ymax <= 51.75""")
    c.execute(f"""copy (select d.id as region_id, d.nm as region_name, a.geometry
        from d join a on a.division_id = d.id left join d p on d.parent_division_id = p.id
        where d.subtype = 'county' and d.nm in (select unnest($names))) to '{ART / 'boroughs.parquet'}' (format parquet)""",
              {"names": LONDON_33})
    n = c.execute(f"select count(*), count(distinct region_id) from read_parquet('{ART / 'boroughs.parquet'}')").fetchall()[0]
    with open(OUT / "boroughs.json", "w", encoding="utf-8") as f:
        json.dump({"release": RELEASE, "boroughs": n[1], "rows": n[0]}, f, indent=1)
    print("boroughs", n)


def population():
    """Kontur population (H3 resolution 8, 2023-11-01, CC BY 4.0) for Great Britain, cut to the box."""
    gz = ART / "kontur_population_GB_20231101.gpkg.gz"
    gp = ART / "kontur_population_GB_20231101.gpkg"
    if not gz.exists():
        urllib.request.urlretrieve(KONTUR, gz)
    if not gp.exists():
        with gzip.open(gz) as src, open(gp, "wb") as dst:
            shutil.copyfileobj(src, dst)
    c = duck()
    c.execute(f"""copy (select h3, population from st_read('{gp}')
        where st_x(st_centroid(st_transform(geom, 'EPSG:3857', 'OGC:CRS84', true))) between {BBOX[0]} and {BBOX[2]}
          and st_y(st_centroid(st_transform(geom, 'EPSG:3857', 'OGC:CRS84', true))) between {BBOX[1]} and {BBOX[3]})
        to '{ART / 'population_h3r8.parquet'}' (format parquet)""")
    n = c.execute(f"select count(*), sum(population) from read_parquet('{ART / 'population_h3r8.parquet'}')").fetchall()[0]
    with open(OUT / "population.json", "w", encoding="utf-8") as f:
        json.dump({"source": KONTUR, "cells": n[0], "population_in_box": n[1]}, f, indent=1)


def compare():
    sh(sys.executable, SKILL / "poi_compare.py", ART / "coffee.parquet", ART / "boroughs.parquet",
       OUT / "boroughs_coffee.csv", "--population", ART / "population_h3r8.parquet", "--within-m", 500)
    top20()


def osm():
    """amenity=cafe from our own Overpass (OSM data of 2025-09-14), nodes and the centres of ways."""
    s, w, n, e = BBOX[1], BBOX[0], BBOX[3], BBOX[2]
    q = (f'[out:json][timeout:900];(node["amenity"="cafe"]({s},{w},{n},{e});'
         f'way["amenity"="cafe"]({s},{w},{n},{e}););out center tags;')
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "GeoAI-master-skills"})
    with urllib.request.urlopen(req, timeout=1200) as r:
        data = json.load(r)
    rows = []
    for el in data["elements"]:
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        t = el.get("tags", {})
        rows.append((f"{el['type']}/{el['id']}", lon, lat, t.get("brand"), t.get("cuisine")))
    import duckdb
    c = duckdb.connect()
    c.execute("create table o (id varchar, lon double, lat double, brand varchar, cuisine varchar)")
    c.executemany("insert into o values (?, ?, ?, ?, ?)", rows)
    c.execute(f"copy o to '{ART / 'osm_cafe.parquet'}' (format parquet)")
    with open(OUT / "osm_cafe.json", "w", encoding="utf-8") as f:
        json.dump({"server": OVERPASS, "osm_base": data.get("osm3s", {}).get("timestamp_osm_base"),
                   "elements": len(rows), "query": q}, f, indent=1)


def crosscheck():
    """Overture cafe or coffee_shop against OSM amenity=cafe: per H3 r8 cell counts, and the big brands."""
    import duckdb
    import h3
    import numpy as np
    from scipy.stats import spearmanr
    c = duckdb.connect()
    ov = c.execute(f"select lon, lat, brand from read_parquet('{ART / 'cafe_or_coffee.parquet'}')").fetchall()
    os_ = c.execute(f"select lon, lat, brand from read_parquet('{ART / 'osm_cafe.parquet'}')").fetchall()
    def cells(rows):
        d = {}
        for lon, lat, _ in rows:
            if BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]:
                k = h3.latlng_to_cell(lat, lon, 8)
                d[k] = d.get(k, 0) + 1
        return d
    a, b = cells(ov), cells(os_)
    keys = sorted(set(a) | set(b))
    x = np.array([a.get(k, 0) for k in keys])
    y = np.array([b.get(k, 0) for k in keys])
    rho = spearmanr(x, y).statistic
    def brand(rows, names):
        return sum(1 for r in rows if r[2] and any(r[2].lower().startswith(n) for n in names))
    out = {"overture_places": len(ov), "osm_places": len(os_), "cells_with_any": len(keys),
           "spearman_cells_r8": round(float(rho), 4),
           "share_cells_only_overture": round(float(((x > 0) & (y == 0)).mean()), 4),
           "share_cells_only_osm": round(float(((x == 0) & (y > 0)).mean()), 4),
           "brands": {n: {"overture": brand(ov, [n.lower()]), "osm": brand(os_, [n.lower()])}
                      for n in ["Costa", "Starbucks", "Caffè Nero", "Pret A Manger"]}}
    with open(OUT / "crosscheck_osm.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(out)


def sensitivity():
    """How the top clusters move with the resolution and the confidence filter."""
    rows = []
    for name in ["h3r8", "h3r9", "h3r10", "s2l14"]:
        a = json.load(open(OUT / f"hotspots_{name}_audit.json", encoding="utf-8"))
        cl = list(csv.DictReader(open(OUT / f"hotspots_{name}_clusters.csv", encoding="utf-8")))
        rows.append((name, a["points"], a.get("hot_cells", ""), a["clusters"],
                     cl[0]["points"] if cl else "", cl[0]["lat"] if cl else "", cl[0]["lon"] if cl else ""))
    d = ART / "hotspots_conf05"
    sh(sys.executable, SKILL / "grid_hotspots.py", ART / "coffee_conf05.parquet", d, "--grid", "h3", "--res", 9,
       "--bbox", *BBOX)
    a = json.load(open(d / "audit.json", encoding="utf-8"))
    cl = list(csv.DictReader(open(d / "clusters.csv", encoding="utf-8")))
    rows.append(("h3r9_conf05", a["points"], a["hot_cells"], a["clusters"], cl[0]["points"], cl[0]["lat"], cl[0]["lon"]))
    with open(OUT / "sensitivity.csv", "w", encoding="utf-8") as f:
        f.write("setting,places,hot_cells,clusters,top_places,top_lat,top_lon\n")
        for r in rows:
            f.write(",".join(map(str, r)) + "\n")


def maps():
    import duckdb
    import h3
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    c = duckdb.connect()
    c.execute("install spatial; load spatial")
    fig, ax = plt.subplots(figsize=(11, 8), dpi=130)
    for (ring,) in c.execute(f"""with g as (select unnest(st_dump(geometry::geometry)) as part
                                      from read_parquet('{ART / 'boroughs.parquet'}'))
                                 select st_astext(st_exteriorring(part.geom)) from g""").fetchall():
        pts = [tuple(map(float, p.split())) for p in ring[ring.index("(") + 1:-1].split(",")]
        ax.add_patch(Polygon(pts, fill=False, lw=0.4, ec="#888"))
    cells = list(csv.DictReader(open(ART / "hotspots_h3r9" / "cells.csv", encoding="utf-8")))
    top = {str(i) for i in range(1, 21)}
    for r in cells:
        if int(r["count"]) == 0:
            continue
        b = [(lng, lat) for lat, lng in h3.cell_to_boundary(r["cell"])]
        color = "#d7301f" if r["cluster"] in top else ("#fc8d59" if r["hot"] == "1" else "#bdbdbd")
        ax.add_patch(Polygon(b, fc=color, ec="none", alpha=0.9))
    for cl in list(csv.DictReader(open(OUT / "top20_clusters.csv", encoding="utf-8"))):
        ax.annotate(cl["rank"], (float(cl["lon"]), float(cl["lat"])), fontsize=7, ha="center", va="center")
    ax.set_xlim(BBOX[0], BBOX[2])
    ax.set_ylim(BBOX[1], BBOX[3])
    ax.set_aspect(1 / math.cos(math.radians(51.5)))
    ax.set_title(f"London coffee shops, H3 r9: top 20 clusters (red), other hot cells (orange), Overture {RELEASE}")
    fig.savefig(OUT / "top20_clusters.png", bbox_inches="tight")


STEPS = {"fetch": fetch, "extract": extract, "hotspots": hotspots, "boroughs": boroughs, "population": population,
         "compare": compare, "osm": osm, "crosscheck": crosscheck, "sensitivity": sensitivity, "maps": maps}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    for s in (STEPS if sys.argv[1] == "all" else sys.argv[1:]):
        STEPS[s]()
