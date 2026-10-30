"""Tables for the maps: cells as squares with the values to draw, and the wards in the same CRS (EPSG:6677).

uv run --with 'duckdb>=1.5.5' --with numpy --with shapely --with pyproj python scripts/07_maps.py

Writes artifacts/_flood/tokyo23-flood-record-vs-a31a/maps/{cells.csv, wards_6677.parquet}; the squares are then made by
analysis-visualize's context_map.py and drawn by classify_map.py (see README.md).

Columns of cells.csv:
  model_pct   the cell's rank under the static model as a percentile from the top (0 = highest)
  agree       1 both (model top k_A and A31a), 2 model top only, 3 A31a only, 4 neither
  test_cat    for cells flooded in 1997-2019: the agree code; other cells empty (NoData)
  a31a        the A31a maximum depth rank (0 outside)
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import shapely
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / "artifacts/_flood/tokyo23-flood-record-vs-a31a"
OUT = ART / "maps"
OUT.mkdir(exist_ok=True)

c = duckdb.connect()
c.execute("load spatial")
m = c.execute(f"select * from '{ART}/maps_main.parquet' order by cell").fetchnumpy()
n = len(m["cell"])
res = json.loads((ROOT / "projects/_flood/tokyo23-flood-record-vs-a31a/outputs/b1_main.json").read_text())
k_a = res["k_a31a"]
pct = m["rank_model_static"] / n * 100
top = m["rank_model_static"] < int(round(k_a * n))
inA = m["a31a"] > 0
agree = np.where(top & inA, 1, np.where(top, 2, np.where(inA, 3, 4)))
test_cat = np.where(m["test_pos"], agree, -1)
with open(OUT / "cells.csv", "w") as f:
    f.write("cell,ix,iy,x,y,model_pct,agree,test_cat,a31a\n")
    for i in range(n):
        tc = "" if test_cat[i] < 0 else str(test_cat[i])
        f.write(f"{i},{m['ix'][i]},{m['iy'][i]},{m['x'][i]:.1f},{m['y'][i]:.1f},{pct[i]:.4f},{agree[i]},{tc},{m['a31a'][i]}\n")
print("cells", n, "agree counts", np.bincount(agree)[1:].tolist(), "test cells by agree", np.bincount(test_cat[test_cat > 0])[1:].tolist())

t = Transformer.from_crs("EPSG:6668", "EPSG:6677", always_xy=True)
rows = c.execute(f"select name, st_aswkb(geometry) from '{ART}/raw/wards.parquet'").fetchall()
c.execute("create table w (name varchar, wkt varchar)")
for name, wkb in rows:
    g = shapely.transform(shapely.from_wkb(bytes(wkb)), lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))
    c.execute("insert into w values (?, ?)", [name, g.wkt])
c.execute(f"copy (select name, st_geomfromtext(wkt) geometry from w) to '{OUT / 'wards_6677.parquet'}' (format parquet)")
print("wards", len(rows))

# Squares from the known grid (100 m, centres at x, y). analysis-visualize's `context_map.py squares` fits the
# grid with all pairs of centres (Theil-Sen), which did not finish for 66,460 cells; the grid here is known.
size = 100.0
c.execute(f"""copy (select *, st_makeenvelope(x - {size / 2}, y - {size / 2}, x + {size / 2}, y + {size / 2}) geometry
    from read_csv('{OUT / 'cells.csv'}') order by cell) to '{OUT / 'cells_sq.parquet'}' (format parquet)""")
print("squares", c.execute(f"select count(*) from '{OUT / 'cells_sq.parquet'}'").fetchone()[0])
