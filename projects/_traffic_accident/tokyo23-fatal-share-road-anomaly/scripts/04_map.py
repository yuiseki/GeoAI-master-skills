"""Map: the 500 m meshes coloured by -log10 P (B2), with the top 10 of the stratified ranking and of the
total-count ranking outlined.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow --with shapely --with matplotlib \
  python -u scripts/04_map.py

Writes artifacts/.../map_units.parquet, wards.parquet, highlight.csv and outputs/map_anomaly.png (+ .json).
"""
import importlib
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ex = importlib.import_module("03_explore")
an = importlib.import_module("02_anomaly")
OUT, ART = an.OUT, an.ART
CLASSIFY = HERE.parents[3] / ".agents/skills/analysis-visualize/scripts/classify_map.py"
ADMIN = "hf://datasets/yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135/municipalities.parquet"


def main():
    m = pd.read_csv(OUT / "meshes_main.csv", dtype={"unit": str})
    m["minus_log10_P"] = -np.log10(m.P)
    b = np.array([ex.mesh_bounds(u) for u in m.unit])
    m["x0"], m["y0"], m["x1"], m["y1"] = b.T
    c = duckdb.connect()
    c.execute("load spatial")
    c.register("m", m[["unit", "minus_log10_P", "x0", "y0", "x1", "y1"]])
    c.execute(f"copy (select unit, minus_log10_P, st_makeenvelope(x0, y0, x1, y1) geometry from m) "
              f"to '{ART / 'map_units.parquet'}' (format parquet)")
    c.execute(f"copy (select name, geometry from '{ADMIN}' where code5 between '13101' and '13123') "
              f"to '{ART / 'wards.parquet'}' (format parquet)")
    an_top = m.unit.head(10).tolist()
    ct_top = m.sort_values("count_rank").unit.head(10).tolist()
    h = pd.DataFrame([dict(id=u, group="層別の外れ 上位10", rank=i + 1) for i, u in enumerate(an_top)] +
                     [dict(id=u, group="総件数 上位10", rank=i + 1) for i, u in enumerate(ct_top)])
    h.to_csv(ART / "highlight.csv", index=False, encoding="utf-8")
    cmd = [sys.executable, str(CLASSIFY), str(ART / "map_units.parquet"), "unit", "minus_log10_P",
           "--kind", "level", "--unit", "-log10 P (Poisson 二項分布の上側確率)", "--method", "fixed",
           "--thresholds", "0.5", "1", "1.5", "2", "--compare", "quantile", "equal", "--palette", "YlOrRd",
           "--crs", "経緯度 (OGC:CRS84)", "--no-labels", "--expect-units", str(len(m)),
           "--source", "警察庁 交通事故統計オープンデータ 389500a (2019〜2025 年、加工して作成)",
           "--context", str(ART / "wards.parquet"), "--context-crs", "EPSG:4612",
           "--context-source", "jp-admin-2026-09 e6c87b1",
           "--accept-crs-difference", "JGD2000 と CRS84 の差は 1 m 未満で、500 m メッシュの図では見えない",
           "--highlight", str(ART / "highlight.csv"),
           "--title", "道路環境をそろえた死亡事故の外れ (500 m メッシュ) と、総件数の上位",
           "--png", str(OUT / "map_anomaly.png")]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
