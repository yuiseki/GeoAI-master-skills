"""Features per 100 m cell: static ones from the land cover, elevation, population and OSM arrays, and the
history of bear reports from the bear years before the target year only.

Window radii are in cells (100 m): r = 5 is the 11 x 11 square around the cell (about 500 m each way).
Cells outside the grid count as 0 in sums (people, buildings, reports) and are left out of means.
"""

import numpy as np

STATIC_RADII = {"500": 5, "1500": 15}
HIST_RADII = {"cell": 0, "r500": 5, "r1000": 10, "r3000": 30}


def box_sum(a, r):
    if r == 0:
        return a.astype(float)
    c = np.pad(a.astype(float), ((r + 1, r), (r + 1, r)))
    c = c.cumsum(axis=0).cumsum(axis=1)
    k = 2 * r + 1
    return c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]


def box_mean(a, r):
    ok = ~np.isnan(a)
    s = box_sum(np.where(ok, a, 0.0), r)
    n = box_sum(ok.astype(float), r)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, s / np.maximum(n, 1), np.nan)


def static_features(wc, dem, pop, osm):
    """wc, dem, pop, osm: the npz contents (dict-like). Returns name -> [ny, nx] float32."""
    from scipy.ndimage import distance_transform_edt

    f = {}
    for c, name in ((10, "tree"), (40, "crop"), (50, "built"), (30, "grass"), (80, "water")):
        f[name] = wc[f"f{c}"].astype(float)
        for rn, r in STATIC_RADII.items():
            f[f"{name}_{rn}"] = box_mean(f[name], r)
    forest = np.nan_to_num(wc["f10"]) >= 0.5
    f["forest_edge"] = np.where(forest, -distance_transform_edt(forest), distance_transform_edt(~forest)) * 100.0
    f["elev"] = dem["elev"].astype(float)
    f["slope"] = dem["slope"].astype(float)
    f["tpi_500"] = f["elev"] - box_mean(f["elev"], 5)
    p = pop["pop"].astype(float)
    f["pop_500"] = box_sum(p, 5)
    f["pop_2000"] = box_sum(p, 20)
    for k in ("d_road_major", "d_road", "d_track", "d_river", "d_stream", "d_building"):
        f[k] = osm[k].astype(float)
    f["bldg_500"] = box_sum(osm["n_building"].astype(float), 5)
    return {k: v.astype(np.float32) for k, v in f.items()}


def history_features(counts, target):
    """History of reports from the bear years before `target` (counts: year -> [ny, nx]).

    Each year's counts are divided by that year's total, so years with ten times the reports weigh the same;
    the all-years features are the mean of those shares over the past years.
    """
    from scipy.ndimage import distance_transform_edt

    past = sorted(y for y in counts if y < target)
    if not past:
        raise ValueError(f"no bear year before {target}")
    share = {y: counts[y] / max(counts[y].sum(), 1.0) for y in past}
    f = {}
    for rn, r in HIST_RADII.items():
        f[f"h_prev_{rn}"] = box_sum(share[past[-1]], r) * 1e4
        f[f"h_all_{rn}"] = sum(box_sum(share[y], r) for y in past) / len(past) * 1e4
    any_past = sum(counts[y] for y in past) > 0
    f["h_dist"] = distance_transform_edt(~any_past) * 100.0 if any_past.any() else np.full(any_past.shape, np.nan)
    return {k: v.astype(np.float32) for k, v in f.items()}
