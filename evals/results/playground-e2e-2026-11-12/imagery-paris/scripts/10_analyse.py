"""Tables, position check against OSM, lean repeatability, grid aggregation."""
import json, math, os
import numpy as np, pandas as pd, h3
from shapely.geometry import shape
ART = "/work/artifacts/paris11-street-imagery"
poles = pd.read_csv(f"{ART}/poles/poles.csv"); man = pd.read_csv(f"{ART}/manifest.csv")
R = {}
R["pictures"] = len(man); R["detections_pole_like"] = len(poles)
R["with_position"] = int(poles.lat.notna().sum()); R["corrected"] = int(poles.corrected.sum())
poles["h_px"] = poles.y1 - poles.y0
# usable lean: corrected and tall (>= 300 px of a 1024-px view) and score >= 0.3
use = poles[(poles.corrected) & (poles.h_px >= 300)].copy()
R["lean_usable"] = len(use)
R["lean_abs_median"] = float(use.lean_deg.abs().median()); R["lean_abs_p90"] = float(use.lean_deg.abs().quantile(.9))
for t in (2, 3, 5): R[f"lean_gt_{t}deg"] = int((use.lean_deg.abs() > t).sum())
R["veg_gt_0.1"] = int((poles.veg_share > .1).sum()); R["veg_gt_0.3"] = int((poles.veg_share > .3).sum())
R["veg_median"] = float(poles.veg_share.median())
# ---- position vs OSM lamps (metric: local equirectangular, Paris lat)
osm = json.load(open(f"{ART}/osm_poles.json"))["elements"]
O = np.array([[e["lon"], e["lat"]] for e in osm]); lat0 = 48.86
def xy(lon, lat): return np.c_[np.radians(lon) * 6371008.8 * math.cos(math.radians(lat0)), np.radians(lat) * 6371008.8]
from scipy.spatial import cKDTree
tree = cKDTree(xy(O[:, 0], O[:, 1]))
pl = poles[poles.lat.notna()].copy()
rows = []
for hgt in (1.5, 2.0, 2.5, 3.0, 3.5):
    # distance scales linearly with the camera height assumed; recompute positions from the camera point
    m = man.set_index("id").loc[pl.picture]
    d = pl.distance_m.values * hgt / 2.5
    b = np.radians(pl.bearing.values)
    base = xy(m.lon.values, m.lat.values)
    p = base + np.c_[d * np.sin(b), d * np.cos(b)]
    dist, _ = tree.query(p)
    # null: same bearing, random distance 3..30 m reshuffled among detections
    rng = np.random.default_rng(0)
    pn = base + np.c_[rng.permutation(d) * np.sin(b), rng.permutation(d) * np.cos(b)]
    dn, _ = tree.query(pn)
    rows.append({"camera_height_m": hgt, "n": len(pl), "median_dist_to_osm_lamp_m": float(np.median(dist)),
                 "share_within_5m": float((dist <= 5).mean()), "null_share_within_5m": float((dn <= 5).mean())})
pd.DataFrame(rows).to_csv("outputs/10_position_vs_osm.csv", index=False, encoding="utf-8")
# ---- lean repeatability across pictures of one site (corrected, tall)
sites = []
for sid, g in use[use.site.notna()].groupby("site"):
    if g.picture.nunique() >= 2:
        x = g.groupby("picture").lean_deg.mean()
        sites.append({"site": int(sid), "n_pictures": len(x), "sd": float(x.std(ddof=1)), "range": float(x.max() - x.min()),
                      "mean": float(x.mean())})
S = pd.DataFrame(sites); S.to_csv("outputs/10_site_repeat.csv", index=False, encoding="utf-8")
R["sites_with_repeat"] = len(S)
if len(S):
    R["repeat_sd_median_deg"] = float(S.sd.median()); R["repeat_sd_rms_deg"] = float(np.sqrt((S.sd ** 2).mean()))
    R["repeat_range_median_deg"] = float(S.range.median())
# ---- grid
pl["cell"] = [h3.latlng_to_cell(a, b, 9) for a, b in zip(pl.lat, pl.lon)]
dmg = pd.read_csv("outputs/06_damage_pictures.csv").merge(man[["id", "lat", "lon"]], left_on="picture", right_on="id")
dmg["cell"] = [h3.latlng_to_cell(a, b, 9) for a, b in zip(dmg.lat, dmg.lon)]
cells = dmg.groupby("cell").agg(pictures=("picture", "size"), damage_share_mean=("share_damaged", "mean")).reset_index()
pc = pl.groupby("cell").agg(pole_detections=("picture", "size"), veg_share_mean=("veg_share", "mean"), veg_gt_0_1=("veg_share", lambda s: int((s > .1).sum()))).reset_index()
u = use[use.lat.notna()].copy(); u["cell"] = [h3.latlng_to_cell(a, b, 9) for a, b in zip(u.lat, u.lon)]
lc = u.groupby("cell").agg(lean_n=("lean_deg", "size"), lean_abs_median=("lean_deg", lambda s: s.abs().median())).reset_index()
G = cells.merge(pc, on="cell", how="outer").merge(lc, on="cell", how="outer")
G["lat"] = [h3.cell_to_latlng(c)[0] for c in G.cell]; G["lon"] = [h3.cell_to_latlng(c)[1] for c in G.cell]
G.to_csv("outputs/10_grid_h3r9.csv", index=False, encoding="utf-8")
R["cells"] = len(G)
json.dump(R, open("outputs/10_summary.json", "w", encoding="utf-8"), indent=1)
print(json.dumps(R, indent=1)); print(pd.DataFrame(rows).to_string())
