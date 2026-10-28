"""Neighbouring municipalities of one prefecture from the polygons of jp-admin-2026-09.

Two municipalities are neighbours when their polygons intersect (ST_Intersects, as the card says: the
polygons overlap a little along borders, so ST_Touches would miss most pairs). Pairs that meet at
a single corner are kept too; how many there are is printed. Only neighbours inside the prefecture are
listed: the counts of municipalities across its border are not in the data.

Usage:
    uvx --from 'duckdb>=1.5.5' python build_adjacency.py PREF_CODE OUT.parquet     # PREF_CODE like 05
"""

import sys

import duckdb

ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"

pref, out = sys.argv[1], sys.argv[2]
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
con.execute(f"""CREATE TABLE a AS SELECT code5, name, ST_GeomFromWKB(ST_AsWKB(geometry)) AS g
                FROM read_parquet('{ADMIN}') WHERE pref_code = '{pref}' AND ward IS NULL AND geometry IS NOT NULL""")
con.execute("""CREATE TABLE pairs AS
    SELECT x.code5 AS code5_a, y.code5 AS code5_b, x.name AS name_a, y.name AS name_b,
           ST_Dimension(ST_Intersection(x.g, y.g)) AS dim
    FROM a x JOIN a y ON x.code5 < y.code5 AND ST_Intersects(x.g, y.g)""")
n = con.execute("SELECT count(*) FROM a").fetchone()[0]
print("municipalities:", n)
print("neighbour pairs:", con.execute("SELECT count(*) FROM pairs").fetchone()[0],
      "| of which the intersection is 0-dimensional (a corner):", con.execute("SELECT count(*) FROM pairs WHERE dim = 0").fetchone()[0])
print("degree per municipality (name, neighbours):", con.execute("""
    SELECT name, count(*) FROM (SELECT name_a AS name FROM pairs UNION ALL SELECT name_b FROM pairs) GROUP BY ALL ORDER BY 2 DESC, 1""").fetchall())
iso = con.execute("SELECT name FROM a WHERE code5 NOT IN (SELECT code5_a FROM pairs UNION SELECT code5_b FROM pairs)").fetchall()
print("without a neighbour in the prefecture:", iso)
con.execute(f"COPY (SELECT code5_a, code5_b, name_a, name_b FROM pairs ORDER BY 1, 2) TO '{out}' (FORMAT PARQUET)")
print("wrote", out)
