"""The B1 and B2 differences within each period, and a period-adjusted difference (exploratory, added after the results).

uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow python scripts/03_within_period.py

The plan's B1 rule asks only that the difference be above 0 in each period, which a difference of 0.002 passes.
This adds, for each period, the 90% interval from resampling that period's disaster days, and the difference
adjusted for period: the two within-period differences weighted by the units at or above the cut in each period.
Writes outputs/within_period.json.
"""
import importlib.util
import json
from pathlib import Path

import pandas as pd

from overfloor import boot_by_day, share

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("blocks", HERE / "02_blocks.py")
bl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bl)
PERIODS = ("first", "second")


def adjusted(f, weight):
    def g(d):
        parts = [(f(d[d["period"] == p]), weight(d[d["period"] == p])) for p in PERIODS]
        w = sum(n for _, n in parts)
        return sum(v * n for v, n in parts) / w if w else float("nan")
    return g


def block(d, f, weight):
    r = {p: {"d": f(d[d["period"] == p]), "ci90": bl.ci(boot_by_day(d[d["period"] == p], f))} for p in PERIODS}
    g = adjusted(f, weight)
    r["adjusted"] = {"d": g(d), "ci90": bl.ci(boot_by_day(d, g))}
    r["share_all_bands_by_period"] = {p: share(d[d["period"] == p]) for p in PERIODS}
    return r


def main():
    u = pd.read_parquet(bl.ART / "units.parquet")
    wn = u[u["ward"] & (u["cls"] == "naisui") & u["rain"].notna()]
    out = {"B1": block(wn, bl.diff_at(70), lambda x: int((x["rain"] >= 70).sum()))}
    x = u[u["rain"].notna() & u["ward"] & (u["rain"] < 50) & u["cls"].isin(["issui", "naisui"])]
    out["B2"] = block(x, lambda y: share(y[y["cls"] == "issui"]) - share(y[y["cls"] == "naisui"]),
                      lambda y: int((y["cls"] == "issui").sum()))
    (HERE.parent / "outputs/within_period.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n")
    print(json.dumps(out, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
