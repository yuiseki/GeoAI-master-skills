"""Gate 5: is the stratified residual of the 500 m meshes spatially autocorrelated? (Moran's I, k = 8 neighbours.)

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pandas --with pyarrow --with scikit-learn \
  python -u scripts/05_moran.py

Value: z = (O - E) / sqrt(V) per mesh, with E and V from the leave-mesh-out shares of meshes_main.csv
recomputed here (V = sum p(1 - p)). Writes artifacts/.../moran_input.parquet and outputs/moran.txt.
"""
import importlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
an = importlib.import_module("02_anomaly")
ex = importlib.import_module("03_explore")
import fatalshare as fs  # noqa: E402

SCRIPT = HERE.parents[3] / ".agents/skills/spatial-autocorrelation/scripts/spatial_autocorrelation.py"


def main():
    d = an.load()
    lab, _ = an.strata(d)
    p = fs.leave_unit_out_p(lab, d.m500.values, d.fatal.values, {})
    g = pd.DataFrame({"unit": d.m500.values, "o": d.fatal.values, "p": p, "v": p * (1 - p)}).groupby("unit").sum()
    g = g[g.v > 0].reset_index()
    g["z"] = (g.o - g.p) / np.sqrt(g.v)
    b = np.array([ex.mesh_bounds(u) for u in g.unit])
    g["lon"], g["lat"] = (b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2
    path = an.ART / "moran_input.parquet"
    g[["unit", "z", "lon", "lat"]].to_parquet(path)
    r = subprocess.run([sys.executable, str(SCRIPT), str(path), "unit", "z", "--lon", "lon", "--lat", "lat",
                        "--k", "8", "--bands-km", "0", "0.75", "1.5", "3", "6", "--permutations", "999"],
                       check=True, capture_output=True, text=True)
    text = f"meshes {len(g)} (of {d.m500.nunique()}; meshes with V = 0 left out)\n" + r.stdout
    (an.OUT / "moran.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
