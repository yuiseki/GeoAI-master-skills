"""Final tables. Reads 14_poles_lean.csv (verified boxes, lean by shear search), labels, OSM; writes outputs."""
import sys, json, math
sys.path.insert(0, "/work/.agents/skills/street-imagery-inspection/scripts")
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from inspect_views import merge_points
ART = "/work/artifacts/paris11-street-imagery"
R = {}
p = pd.read_csv("outputs/14_poles_lean.csv"); man = pd.read_csv(f"{ART}/manifest.csv")
R["pictures"] = len(man); R["boxes"] = len(p); R["boxes_verified"] = int(p.verified.sum())
v = p[p.verified].copy()
R["verified_with_position"] = int(v.lat.notna().sum())
# --- sites among verified boxes with positions (4 m single linkage)
vp = v[v.lat.notna()].copy()
vp["vsite"] = merge_points(list(zip(vp.lat, vp.lon)), 4.0)
R["sites"] = int(vp.vsite.nunique())
s_pic = vp.groupby("vsite").picture.nunique(); R["sites_seen_in_2plus_pictures"] = int((s_pic >= 2).sum())
# --- usable lean: verified, corrected, tall, not saturated
use = v[(v.corrected) & (v.h_px >= 250) & v.lean_grad_deg.notna() & (v.raw_grad_deg.abs() < 9.9)].copy()
R["lean_usable_boxes"] = len(use)
a = use.lean_grad_deg.abs()
R["lean_abs_median"] = float(a.median()); R["lean_abs_p90"] = float(a.quantile(.9))
for t in (1, 2, 3, 5): R[f"lean_gt_{t}deg"] = int((a > t).sum())
R["raw_abs_median_before_roll_correction"] = float(use.raw_grad_deg.abs().median())
R["hough_lean_available_of_verified"] = int(v.lean_deg.notna().sum())
R["grad_lean_available_of_verified"] = int(v.lean_grad_deg.notna().sum())
both = v[v.lean_deg.notna() & v.lean_grad_deg.notna()]
R["hough_vs_shear_n"] = len(both); R["hough_vs_shear_corr"] = float(np.corrcoef(both.lean_deg, both.lean_grad_deg)[0, 1])
R["hough_vs_shear_median_abs_diff"] = float((both.lean_deg - both.lean_grad_deg).abs().median())
# --- repeatability: same site, different pictures (independent frames, other viewing direction)
use = use.merge(vp[["picture", "yaw", "x0", "vsite"]], on=["picture", "yaw", "x0"], how="left")
rows = []
for sid, g in use[use.vsite.notna()].groupby("vsite"):
    x = g.groupby("picture").lean_grad_deg.mean()
    if len(x) >= 2: rows.append({"site": int(sid), "n_pictures": len(x), "sd": float(x.std(ddof=1)), "range": float(x.max() - x.min())})
S = pd.DataFrame(rows); S.to_csv("outputs/15_site_repeat.csv", index=False, encoding="utf-8")
R["repeat_sites"] = len(S)
if len(S):
    R["repeat_sd_median"] = float(S.sd.median()); R["repeat_sd_rms"] = float(np.sqrt((S.sd ** 2).mean()))
    R["repeat_range_median"] = float(S.range.median()); R["repeat_range_max"] = float(S.range.max())
# --- tilt candidates: |lean| >= 3 deg
cand = use[use.lean_grad_deg.abs() >= 3].sort_values("lean_grad_deg").reset_index(drop=True)
cand.insert(0, "cno", range(1, len(cand) + 1)); cand.to_csv("outputs/15_tilt_candidates.csv", index=False, encoding="utf-8")
R["tilt_candidates_ge3deg"] = len(cand)
# --- vegetation vs AI labels
vs = pd.read_csv("outputs/review/veg_sample.csv").merge(pd.read_csv("outputs/review/veg_labels.csv"), on="vno")
R["veg_labeled_n"] = len(vs); R["veg_adjacent_share"] = float(vs.foliage_adjacent.mean())
R["veg_auc"] = float(roc_auc_score(vs.foliage_adjacent, vs.veg_share))
vt = []
for th in (0.05, 0.1, 0.2, 0.3):
    f = vs.veg_share >= th
    vt.append({"threshold": th, "flagged": int(f.sum()), "precision": float((vs.foliage_adjacent[f] == 1).mean()) if f.any() else None, "recall": float(f[vs.foliage_adjacent == 1].mean())})
pd.DataFrame(vt).to_csv("outputs/15_veg_thresholds.csv", index=False, encoding="utf-8")
vv = v.copy(); R["verified_veg_ge_0.2"] = int((vv.veg_share >= .2).sum()); R["verified_veg_ge_0.2_share"] = float((vv.veg_share >= .2).mean())
R["verified_veg_median"] = float(vv.veg_share.median())
# --- position vs OSM among verified
osm = json.load(open(f"{ART}/osm_poles.json"))["elements"]
from scipy.spatial import cKDTree
lat0 = 48.86
def xy(lon, lat): return np.c_[np.radians(lon) * 6371008.8 * math.cos(math.radians(lat0)), np.radians(lat) * 6371008.8]
tree = cKDTree(xy(np.array([e["lon"] for e in osm]), np.array([e["lat"] for e in osm])))
mm = man.set_index("id"); rows = []
for hgt in (1.5, 2.0, 2.5, 3.0):
    m = mm.loc[vp.picture]; d = vp.distance_m.values * hgt / 2.5; b = np.radians(vp.bearing.values)
    base = xy(m.lon.values, m.lat.values); pos = base + np.c_[d * np.sin(b), d * np.cos(b)]
    dist, _ = tree.query(pos)
    null = []
    for k in range(200):
        rng = np.random.default_rng(k); pn = base + np.c_[rng.permutation(d) * np.sin(b), rng.permutation(d) * np.cos(b)]
        null.append((tree.query(pn)[0] <= 5).mean())
    rows.append({"camera_height_m": hgt, "n": len(vp), "median_dist_m": float(np.median(dist)), "within_5m": float((dist <= 5).mean()),
                 "null_within_5m_mean": float(np.mean(null)), "null_within_5m_p95": float(np.percentile(null, 95))})
pd.DataFrame(rows).to_csv("outputs/15_position_vs_osm.csv", index=False, encoding="utf-8")
R["osm_street_lamps"] = len(osm)
# --- road
pt = pd.read_csv("outputs/06_damage_patches.csv"); R["road_patches"] = len(pt); R["road_patches_ge_0.5"] = int((pt.p_damage >= .5).sum())
R["road_patches_ge_0.6"] = int((pt.p_damage >= .6).sum()); R["road_pictures_with_patch_ge_0.6"] = int((pt.groupby("picture").p_damage.max() >= .6).sum())
rl = pd.read_csv("outputs/review/road_patch_labels.csv"); rl["band"] = pd.cut(rl.p_damage, [0, .2, .5, .6, .69, 1.01], right=False)
bt = rl.groupby("band", observed=True).crack.agg(n_labeled="size", n_crack="sum").reset_index(); bt["band"] = bt.band.astype(str)
cnt = pd.cut(pt.p_damage, [0, .2, .5, .6, .69, 1.01], right=False).value_counts().sort_index(); bt["patches_in_band"] = cnt.values
bt["precision"] = bt.n_crack / bt.n_labeled; bt.to_csv("outputs/15_road_precision_by_band.csv", index=False, encoding="utf-8")
bt["lo"] = [float(x.strip("[)").split(",")[0]) for x in bt.band]
def est(lo):
    b = bt[bt.lo >= lo]; return float((b.precision * b.patches_in_band).sum() / b.patches_in_band.sum())
R["road_est_precision_ge_0.5"] = est(0.5); R["road_est_precision_ge_0.6"] = est(0.6)
# --- grid (H3 res 9) counts
import h3
man["cell"] = [h3.latlng_to_cell(a, b, 9) for a, b in zip(man.lat, man.lon)]
dm = pt.groupby("picture").p_damage.agg(max_p="max", n="size").reset_index()
dm["cand"] = dm.max_p >= .6
g = man.merge(dm, left_on="id", right_on="picture")
cells = g.groupby("cell").agg(pictures=("id", "size"), damage_candidate_pictures=("cand", "sum")).reset_index()
vp["cell"] = [h3.latlng_to_cell(a, b, 9) for a, b in zip(vp.lat, vp.lon)]
pc = vp.groupby("cell").agg(pole_boxes=("picture", "size"), sites=("vsite", "nunique"), veg_ge_0_2=("veg_share", lambda s: int((s >= .2).sum()))).reset_index()
uc = use.merge(vp[["picture", "yaw", "x0", "cell"]], on=["picture", "yaw", "x0"], how="inner")
lc = uc.groupby("cell").agg(lean_n=("lean_grad_deg", "size"), lean_abs_median=("lean_grad_deg", lambda s: s.abs().median()), tilt_ge3=("lean_grad_deg", lambda s: int((s.abs() >= 3).sum()))).reset_index()
G = cells.merge(pc, on="cell", how="outer").merge(lc, on="cell", how="outer").fillna({"pole_boxes": 0, "sites": 0, "veg_ge_0_2": 0, "lean_n": 0, "tilt_ge3": 0})
G["veg_ge_0_2_share"] = G.veg_ge_0_2 / G.pole_boxes.replace(0, np.nan)
G["damage_candidate_share"] = G.damage_candidate_pictures / G.pictures
G["lat"] = [h3.cell_to_latlng(c)[0] for c in G.cell]; G["lon"] = [h3.cell_to_latlng(c)[1] for c in G.cell]
G.to_csv("outputs/15_grid_h3r9.csv", index=False, encoding="utf-8"); R["cells"] = len(G); R["cells_with_ge10_pictures"] = int((G.pictures >= 10).sum())
vp.to_csv("outputs/15_pole_sightings_with_position.csv", index=False, encoding="utf-8")
# sites table
st = vp.drop(columns=["lean_grad_deg"]).merge(use[["picture", "yaw", "x0", "lean_grad_deg"]], on=["picture", "yaw", "x0"], how="left").groupby("vsite").agg(
    lat=("lat", "mean"), lon=("lon", "mean"), sightings=("picture", "size"), pictures=("picture", "nunique"),
    lean_deg_mean=("lean_grad_deg", "mean"), lean_n=("lean_grad_deg", "count"), veg_share_max=("veg_share", "max")).reset_index()
st["foliage_flag_ge_0.2"] = st.veg_share_max >= .2
st.to_csv("outputs/15_pole_sites.csv", index=False, encoding="utf-8")
json.dump(R, open("outputs/15_summary.json", "w", encoding="utf-8"), indent=1)
print(json.dumps(R, indent=1))
print(pd.DataFrame(vt).to_string()); print(pd.DataFrame(rows).to_string()); print(bt.to_string()); print(S.describe().to_string() if len(S) else "")
