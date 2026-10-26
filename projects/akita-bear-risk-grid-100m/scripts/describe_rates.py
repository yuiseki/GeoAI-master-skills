"""Share of cells with a bear report in a bear year, by bands of the distance to the forest edge and to the
nearest building (description of the data, not of the model). Writes a CSV.

Usage:
    ... python describe_rates.py ART_DIR YEAR OUT.csv
"""

import sys

import numpy as np
import pandas as pd

import features as ft


def main():
    art, year, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    wc, dem, pop, osm = (np.load(f"{art}/{n}.npz") for n in ("worldcover", "dem", "worldpop", "osm"))
    st = ft.static_features(wc, dem, pop, osm)
    muni = np.load(f"{art}/grid_mask.npz")["muni"]
    inside = muni >= 0
    pos = np.load(f"{art}/reports_by_year.npz")[f"c{year}"][inside] > 0
    edge = st["forest_edge"][inside]
    bld = st["d_building"][inside]
    # forest_edge: forest cells hold minus the distance to the nearest non-forest cell (-100 at the edge),
    # other cells the distance to the nearest forest cell (100 next to it); distances are between cell centres
    edge_bins = [-1e9, -1000.5, -300.5, -100.5, 0, 100.5, 300.5, 1000.5, 1e9]
    edge_lab = ["森の中 1 km 超", "森の中 300 m〜1 km", "森の中 100〜300 m", "森の縁のセル", "森の隣のセル",
                "森まで 100〜300 m", "森まで 300 m〜1 km", "森まで 1 km 超"]
    bld_bins = [-1, 0.5, 100.5, 300.5, 1000.5, 1e9]
    bld_lab = ["建物のあるセル", "建物の隣のセル", "建物まで 100〜300 m", "建物まで 300 m〜1 km", "建物まで 1 km 超"]
    df = pd.DataFrame({"edge": pd.cut(edge, edge_bins, labels=edge_lab, right=False), "bld": pd.cut(bld, bld_bins, labels=bld_lab), "pos": pos})
    t = df.groupby(["bld", "edge"], observed=True).pos.agg(["size", "mean", "sum"]).reset_index()
    t.columns = ["building", "forest_edge", "cells", "share_with_report", "cells_with_report"]
    m1 = df.groupby("edge", observed=True).pos.agg(["size", "mean", "sum"]).reset_index()
    m1.columns = ["forest_edge", "cells", "share_with_report", "cells_with_report"]
    m1.insert(0, "building", "(all)")
    m2 = df.groupby("bld", observed=True).pos.agg(["size", "mean", "sum"]).reset_index()
    m2.columns = ["building", "cells", "share_with_report", "cells_with_report"]
    m2.insert(1, "forest_edge", "(all)")
    t = pd.concat([m1, m2, t], ignore_index=True)
    t.to_csv(out, index=False)
    print(df.groupby("edge", observed=True).pos.agg(["size", "mean"]).round(5).to_string())
    print(df.groupby("bld", observed=True).pos.agg(["size", "mean"]).round(5).to_string())
    near = df[df.bld == "建物のあるセル"].groupby("edge", observed=True).pos.agg(["size", "mean"]).round(4)
    print("cells holding a building, by the forest edge:\n" + near.to_string())


if __name__ == "__main__":
    main()
