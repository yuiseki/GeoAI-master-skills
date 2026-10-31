"""Functions for the flood detection of stage A (see EXPERIMENT_PLAN.md, 判定の手順).

Arrays are 2-D on one 10 m grid; nan is a missing value. Connectivity is 4-neighbour throughout.
"""
import numpy as np
from scipy import ndimage

FOUR = ndimage.generate_binary_structure(2, 1)


def to_db(lin):
    """10 log10 of a linear backscatter; values <= 0 or nan become nan."""
    lin = np.asarray(lin, float)
    out = np.full(lin.shape, np.nan)
    ok = lin > 0
    out[ok] = 10 * np.log10(lin[ok])
    return out


def gauss_posterior(x, mu_w, sd_w, mu_l, sd_l):
    """P(water | x) from two normal likelihoods with equal priors; nan where x is nan."""
    x = np.asarray(x, float)
    lw = -0.5 * ((x - mu_w) / sd_w) ** 2 - np.log(sd_w)
    ll = -0.5 * ((x - mu_l) / sd_l) ** 2 - np.log(sd_l)
    return 1 / (1 + np.exp(np.clip(ll - lw, -700, 700)))


def components(mask, min_size):
    """Label the 4-connected parts of mask, keeping parts of at least min_size pixels (others 0)."""
    lab, n = ndimage.label(mask, structure=FOUR)
    if n == 0:
        return lab
    size = np.bincount(lab.ravel())
    keep = size >= min_size
    keep[0] = False
    new = np.zeros(n + 1, int)
    new[keep] = np.arange(1, keep.sum() + 1)
    return new[lab]


def edge_quantile(labels, dem, q=0.5):
    """For each label, the q quantile of dem over its edge pixels (a pixel of the part with a 4-neighbour outside it).

    Edge pixels with nan dem are left out; a part with no usable edge pixel gets nan.
    """
    out = {}
    pad = np.pad(labels, 1, constant_values=0)
    inner = pad[1:-1, 1:-1]
    edge = np.zeros(labels.shape, bool)
    for sl in ((slice(None, -2), slice(1, -1)), (slice(2, None), slice(1, -1)),
               (slice(1, -1), slice(None, -2)), (slice(1, -1), slice(2, None))):
        edge |= pad[sl] != inner
    edge &= labels > 0
    for k in range(1, labels.max() + 1):
        v = dem[edge & (labels == k)]
        v = v[~np.isnan(v)]
        out[k] = float(np.quantile(v, q)) if len(v) else np.nan
    return out


def floodable(labels, levels, dem, passable):
    """Pixels reachable from each part through pixels with dem <= its level, or passable pixels, or the part itself.

    A nan level gives only the part itself. The result is the union over the parts.
    """
    out = labels > 0
    for k, level in levels.items():
        part = labels == k
        if np.isnan(level):
            continue
        with np.errstate(invalid="ignore"):
            ok = (dem <= level) | passable | part
        lab, _ = ndimage.label(ok, structure=FOUR)
        hit = np.unique(lab[part])
        out |= np.isin(lab, hit[hit > 0])
    return out


def metrics(ref, det, valid, pixel_area=100.0):
    """Areas (m2) and rates of a detection against a reference, counted only where valid."""
    r, d = ref & valid, det & valid
    both = (r & d).sum()
    out = {"ref_m2": r.sum() * pixel_area, "det_m2": d.sum() * pixel_area, "both_m2": both * pixel_area,
           "missed_m2": (r & ~d).sum() * pixel_area, "extra_m2": (d & ~r).sum() * pixel_area}
    out["recall"] = both / r.sum() if r.sum() else np.nan
    out["precision"] = both / d.sum() if d.sum() else np.nan
    return {k: float(v) for k, v in out.items()}


def buffer_for_area(geom, target, lo=0.0, hi=5000.0, tol=0.01):
    """Buffer distance (in the units of geom) whose buffered area is target, by bisection."""
    if geom.buffer(lo).area > target:
        raise ValueError("the geometry is already larger than the target")
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if geom.buffer(mid).area < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


PLAN = {"post": 0.5, "sure": 0.9, "min_size": 100, "level_q": 0.5, "vh_pct": 1.0, "change_pct": 5.0,
        "land_min_elev": 15.0, "use_floodable": True}


def detect(vv_b, vh_b, vv_a, vh_a, dem, water, **kw):
    """The detection of EXPERIMENT_PLAN.md (判定の手順 1 to 8). Returns the masks and the fitted values.

    vv_*, vh_* are in dB (b before, a after); dem in m; water is the permanent water mask. Keyword arguments override PLAN.
    """
    p = {**PLAN, **kw}
    ok = ~(np.isnan(vv_b) | np.isnan(vh_b) | np.isnan(vv_a) | np.isnan(vh_a))
    dvv, dvh = vv_a - vv_b, vh_a - vh_b
    land = ok & ~water & (dem >= p["land_min_elev"])
    lake = ok & water
    if land.sum() < 100 or lake.sum() < 100:
        raise ValueError(f"too few reference pixels: land {land.sum()}, water {lake.sum()}")
    fit = {"mu_w": float(vv_a[lake].mean()), "sd_w": float(vv_a[lake].std()),
           "mu_l": float(vv_a[land].mean()), "sd_l": float(vv_a[land].std()),
           "dvv_land_pct": float(np.percentile(dvv[land], p["change_pct"])),
           "dvh_land_pct": float(np.percentile(dvh[land], p["vh_pct"])),
           "n_land": int(land.sum()), "n_water": int(lake.sum())}
    prob = np.where(ok, gauss_posterior(vv_a, fit["mu_w"], fit["sd_w"], fit["mu_l"], fit["sd_l"]), np.nan)
    with np.errstate(invalid="ignore"):
        sure = ok & ~water & (prob >= p["sure"]) & (dvv < fit["dvv_land_pct"])
        labels = components(sure, p["min_size"])
        levels = edge_quantile(labels, dem, p["level_q"])
        zone = floodable(labels, levels, dem, water & ok) if p["use_floodable"] else ok.copy()
        det_vv = zone & ok & ~water & (prob >= p["post"])
        det_vvvh = det_vv | (zone & ok & ~water & (dvh <= fit["dvh_land_pct"]))
    fit["n_parts"] = int(labels.max())
    return {"prob": prob, "labels": labels, "levels": levels, "zone": zone, "det_vv": det_vv, "det_vvvh": det_vvvh,
            "dvv": dvv, "dvh": dvh, "ok": ok, "fit": fit, "params": p}
