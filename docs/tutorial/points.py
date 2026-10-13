"""Point data to a prediction, end to end: events -> equal-area grid -> features -> CV that respects space.

    uvx --from 'duckdb>=1.5.5' --with scikit-learn --with pandas --with pyarrow python docs/tutorial/points.py

Reads UCDP GED 26.1 from Hugging Face (needs the network), keeps events whose position is accurate
(where_prec <= 2), projects them to an equal-area CRS (EPSG:6933), counts them per 100 km cell, and
predicts a cell's 2023 count from its 2022 events.
"""

import duckdb
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold, KFold, cross_val_predict

CELL = 100_000  # metres, in EPSG:6933
BLOCK = 10  # cells per side of a CV block (1,000 km)

con = duckdb.connect()
con.sql("install httpfs; load httpfs; install spatial; load spatial")
con.sql(f"""
create table ev as
select year,
       cast(floor(ST_X(p) / {CELL}) as int) as cx,
       cast(floor(ST_Y(p) / {CELL}) as int) as cy
from (select year, ST_Transform(geometry, 'OGC:CRS84', 'EPSG:6933', always_xy := true) as p
      from 'hf://datasets/yuiseki/ucdp-ged/parquet/26.1/ged.parquet'
      where year in (2022, 2023) and where_prec <= 2)
""")
n_events = con.sql("select count(*) from ev").fetchone()[0]

# One row per cell that had an event in 2022. Neighbours are the 8 surrounding cells.
con.sql("""
create table cnt as select cx, cy, count(*) filter (where year = 2022) as n22,
                            count(*) filter (where year = 2023) as n23 from ev group by all
""")
t = con.sql("""
select a.cx, a.cy, a.n22, a.n23,
       coalesce((select sum(b.n22) from cnt b where abs(b.cx - a.cx) <= 1 and abs(b.cy - a.cy) <= 1
                 and not (b.cx = a.cx and b.cy = a.cy)), 0) as nb22
from cnt a where a.n22 > 0
""").df()
print(f"events {n_events}, cells with a 2022 event {len(t)}")

y = np.log1p(t["n23"])
base = np.c_[np.log1p(t["n22"]), np.log1p(t["nb22"])]
with_xy = np.c_[base, t["cx"], t["cy"]]
block = (t["cx"] // BLOCK).astype(str) + "_" + (t["cy"] // BLOCK).astype(str)
print(f"1,000 km blocks: {block.nunique()}")

schemes = {
    "KFold (cells at random)": dict(cv=KFold(5, shuffle=True, random_state=0)),
    "GroupKFold (1,000 km blocks)": dict(cv=GroupKFold(5), groups=block),
}
models = {"last year only": (LinearRegression(), np.log1p(t["n22"]).to_numpy().reshape(-1, 1)),
          "linear, + neighbours": (LinearRegression(), base),
          "hgb, + neighbours": (HistGradientBoostingRegressor(random_state=0), base),
          "hgb, + neighbours + x,y": (HistGradientBoostingRegressor(random_state=0), with_xy)}
print(f"{'':<30}" + "".join(f"{m:<26}" for m in models))
for name, args in schemes.items():
    row = []
    for model, X in models.values():
        pred = cross_val_predict(model, X, y, **args)
        row.append(f"R2 {r2_score(y, pred):.3f}")
    print(f"{name:<30}" + "".join(f"{r:<26}" for r in row))
