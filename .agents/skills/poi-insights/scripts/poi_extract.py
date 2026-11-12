"""Extract points of interest (POI) of some categories in a bounding box from a table with the Overture places
columns, and count what happened to every row.

    uvx --from 'duckdb>=1.5.5' python poi_extract.py SOURCE OUT.parquet --bbox W S E N \
        [--category coffee_shop cafe] [--exclude-status permanently_closed] [--min-confidence 0.5]

SOURCE is a Parquet path or glob, local or s3:// (the Overture release: s3://overturemaps-us-west-2/release/<release>/
theme=places/type=place/*.parquet, region us-west-2, no credentials). Columns used: id, geometry, bbox, names,
basic_category, taxonomy (primary, hierarchy), brand, operating_status, confidence, sources.

A row is in a category when its basic_category or any level of its taxonomy hierarchy is one of --category, so
"coffee_shop" also takes the coffee roasteries filed under it. A missing operating_status is kept and written as
"unknown": it is not evidence that the place is open. Every row in the box is counted once: other_category,
excluded_status, low_confidence (in that order) or kept. OUT.audit.json records the source, filters and counts.
"""

import argparse
import json
import sys

import duckdb


def _connect(source):
    c = duckdb.connect()
    c.sql("install spatial; load spatial")
    if source.startswith("s3://"):
        c.sql("install httpfs; load httpfs; set s3_region = 'us-west-2'")
    return c


def extract(source, bbox, categories, exclude_status=(), min_confidence=0.0, con=None):
    """Rows (dicts) kept and the counts of every row in the box."""
    w, s, e, n = bbox
    c = con or _connect(source)
    cats = list(categories)
    c.execute(f"""create or replace temp table poi as
        select id, names."primary" as name, basic_category as category,
               array_to_string(taxonomy.hierarchy, '>') as hierarchy,
               brand.names."primary" as brand,
               coalesce(operating_status, 'unknown') as operating_status,
               confidence,
               array_to_string(list_distinct([x.dataset for x in sources]), ';') as sources,
               st_x(geometry) as lon, st_y(geometry) as lat,
               coalesce({'true' if not cats else 'basic_category in (select unnest($cats)) or len(list_intersect(coalesce(taxonomy.hierarchy, []), $cats)) > 0'}, false) as in_cat
        from read_parquet('{source}')
        where bbox.xmin >= {w} and bbox.xmax <= {e} and bbox.ymin >= {s} and bbox.ymax <= {n}""",
          {"cats": cats} if cats else None)
    ex = list(exclude_status)
    counts = c.execute("""select count(*),
                             count(*) filter (where not in_cat),
                             count(*) filter (where in_cat and operating_status in (select unnest($ex))),
                             count(*) filter (where in_cat and operating_status not in (select unnest($ex))
                                                  and coalesce(confidence, 0) < $mc)
                      from poi""", {"ex": ex or [""], "mc": min_confidence}).fetchall()[0]
    cur = c.execute("""select * exclude (in_cat) from poi
                    where in_cat and operating_status not in (select unnest($ex)) and coalesce(confidence, 0) >= $mc
                    order by id""", {"ex": ex or [""], "mc": min_confidence})
    cols = [d[0] for d in cur.description]
    kept = [dict(zip(cols, r)) for r in cur.fetchall()]
    audit = {"in_bbox": counts[0], "other_category": counts[1], "excluded_status": counts[2],
             "low_confidence": counts[3], "kept": len(kept)}
    if sum(v for k, v in audit.items() if k != "in_bbox") != audit["in_bbox"]:
        raise SystemExit(f"rows do not add up: {audit}")
    return kept, audit


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source")
    p.add_argument("out")
    p.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("W", "S", "E", "N"))
    p.add_argument("--category", nargs="*", default=[])
    p.add_argument("--exclude-status", nargs="*", default=["permanently_closed"])
    p.add_argument("--min-confidence", type=float, default=0.0)
    a = p.parse_args(argv)
    c = _connect(a.source)
    rows, audit = extract(a.source, a.bbox, a.category, a.exclude_status, a.min_confidence, con=c)
    c.execute(f"copy (select * exclude (in_cat) from poi where in_cat and operating_status not in "
          f"(select unnest($ex)) and coalesce(confidence, 0) >= $mc order by id) to '{a.out}' (format parquet)",
          {"ex": a.exclude_status or [""], "mc": a.min_confidence})
    meta = {"source": a.source, "bbox": a.bbox, "category": a.category, "exclude_status": a.exclude_status,
            "min_confidence": a.min_confidence, "counts": audit, "duckdb": duckdb.__version__}
    with open(a.out + ".audit.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(json.dumps(audit))


if __name__ == "__main__":
    sys.exit(main())
