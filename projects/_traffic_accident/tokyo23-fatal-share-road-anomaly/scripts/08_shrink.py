"""B9 (exploratory): stratum shares pulled toward the parent stratum, m = 210, for every unit.

systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pandas --with pyarrow python -u scripts/08_shrink.py

Same strata, P and BH as 02_anomaly.py; only the death probability changes to
fatalshare.leave_unit_out_p_shrunk (m = 210). Units: 500 m (main), 1 km, 250 m meshes and the road links of
06_links.py (artifacts/.../accident_links.parquet). Compares each with the plain version (02 and 06 outputs).
Writes outputs/shrink.csv, outputs/meshes_main_shrunk.csv, outputs/links_top20_shrunk.csv.
"""
import importlib
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
an = importlib.import_module("02_anomaly")
import fatalshare as fs  # noqa: E402

M = 210


def main():
    d = an.load()
    lk = pd.read_parquet(an.ART / "accident_links.parquet")
    d = d.merge(lk, on=["file_year", "station", "no"], how="left", validate="one_to_one")
    assert d.link.notna().all()
    shrunk = lambda s, u, f: fs.leave_unit_out_p_shrunk(s, u, f, M)  # noqa: E731
    plain_top = {"m500": pd.read_csv(an.OUT / "meshes_main.csv", dtype={"unit": str}).unit.head(10).tolist(),
                 "m1000": pd.read_csv(an.OUT / "meshes_m1000.csv", dtype={"unit": str}).unit.head(10).tolist(),
                 "m250": pd.read_csv(an.OUT / "meshes_m250.csv", dtype={"unit": str}).unit.head(10).tolist(),
                 "link": pd.read_csv(an.OUT / "links_top20.csv").unit.head(10).tolist()}
    rows = []
    for col in ("m500", "m1000", "m250", "link"):
        dd = d[d.link >= 0].reset_index(drop=True) if col == "link" else d
        m, lab, _ = an.score(dd, col, p_fn=shrunk)
        if col == "m500":
            m.to_csv(an.OUT / "meshes_main_shrunk.csv", index=False, encoding="utf-8")
        if col == "link":
            m.head(20).to_csv(an.OUT / "links_top20_shrunk.csv", index=False, encoding="utf-8")
        top = m.unit.head(10).tolist()
        rows.append(dict(unit=col, m=M, units=int(len(m)), q_lt_005=int((m.q < 0.05).sum()),
                         q_lt_010=int((m.q < 0.10).sum()), P_zero=int((m.P == 0).sum()), min_P=float(m.P.min()),
                         min_q=float(m.q.min()), E_total=round(float(m.E.sum()), 2), O_total=int(m.O.sum()),
                         common_top10_with_plain=len(set(map(str, top)) & set(map(str, plain_top[col]))),
                         top10=" ".join(map(str, top))))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(an.OUT / "shrink.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
