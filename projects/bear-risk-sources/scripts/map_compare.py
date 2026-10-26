"""Side-by-side maps of one held-out region: the model fitted on the other three regions with the base features and
with the climate normals added, as rank classes, with the region's report cells on top.

Usage:
    ... python map_compare.py TARGET OUT.png
"""

import json
import sys

import numpy as np

import run_matrix as rm

CLASSES = [0.01, 0.05, 0.10, 0.25, 0.50]
COLOURS = ["#9b0a19", "#e5543b", "#f59e72", "#facba6", "#fde0c5", "#f2f0f7"]


def classes(score):
    n = len(score)
    share = np.empty(n)
    share[np.argsort(-score, kind="stable")] = (np.arange(n) + 1) / n
    return np.searchsorted(CLASSES, share, side="left")


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.colors import ListedColormap

    target, out = sys.argv[1], sys.argv[2]
    train = [r for r in rm.REGIONS if r != target]
    art = rm.ART[target]
    meta = json.load(open(f"{art}/grid.json"))
    cells = pd.read_parquet(f"{art}/cells.parquet", columns=["ix", "iy"])
    y, _ = rm.labels(target)
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Noto Sans CJK TC", "sans-serif"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 7))
    res = {}
    for ax, v, title in zip(axes, ["base", "clim"], ["基準 (OSM の建物、道路、川)", "平年値を足した"]):
        m = rm.fit(train, v)
        X, _ = rm.design(target, v)
        s = m.predict_proba(X)[:, 1]
        cap = rm.sr.capture(rm.sr.rank_order(s, seed=0), y, 0.05)
        res[v] = cap
        arr = np.full((meta["ny"], meta["nx"]), np.nan)
        arr[cells.iy, cells.ix] = classes(s)
        ax.imshow(arr, origin="lower", cmap=ListedColormap(COLOURS), vmin=-0.5, vmax=5.5, interpolation="nearest")
        py, px = cells.iy.to_numpy()[y], cells.ix.to_numpy()[y]
        ax.scatter(px, py, s=0.4, c="#123a6e", linewidths=0)
        ax.set_title(f"{title}\ncapture@5% = {cap:.3f}", fontsize=10)
        ax.set_xticks([]), ax.set_yticks([])
    fig.suptitle(f"{target} を、ほかの 3 地域 ({' + '.join(train)}) で学習したモデルで当てる。青い点は通報のあったセル", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out, dpi=140)
    json.dump(res, open(out.replace(".png", ".json"), "w"), indent=1)
    print(res)


if __name__ == "__main__":
    main()
