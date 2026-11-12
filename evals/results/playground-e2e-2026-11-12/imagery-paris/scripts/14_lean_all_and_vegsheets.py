import sys, numpy as np, pandas as pd
sys.path.insert(0, "scripts")
from PIL import Image, ImageDraw
from leangrad import lean_grad
ART = "/work/artifacts/paris11-street-imagery"
p = pd.read_csv("outputs/13_poles_verified.csv")
leans = []
cache = {}
for r in p.itertuples():
    k = (r.picture, int(r.yaw))
    if k not in cache: cache = {k: np.asarray(Image.open(f"{ART}/views/{r.picture}_y{int(r.yaw)}.jpg").convert("L"), float)}
    leans.append(lean_grad(cache[k], (r.x0, r.y0, r.x1, r.y1)))
p["raw_grad_deg"] = [np.nan if v is None else v for v in leans]
p["lean_grad_deg"] = np.where(p.corrected, p.raw_grad_deg - p.reference_deg, np.nan)
p["h_px"] = p.y1 - p.y0
p.to_csv("outputs/14_poles_lean.csv", index=False, encoding="utf-8")
print(p[["raw_grad_deg", "lean_grad_deg", "lean_deg"]].describe())
# vegetation sheets: true poles from test+dev, upper 40% region of the (3x wide) box
rows = []
for samp, lab in (("pole_sample", "pole_labels_test"), ("pole_dev_sample", "pole_labels_dev")):
    s = pd.read_csv(f"outputs/review/{samp}.csv").merge(pd.read_csv(f"outputs/review/{lab}.csv")[["no", "is_pole"]], on="no")
    s["set"] = samp; rows.append(s[s.is_pole == 1])
t = pd.concat(rows).reset_index(drop=True); t.insert(0, "vno", range(1, len(t) + 1))
t[["vno", "set", "no", "picture", "yaw", "x0", "veg_share"]].to_csv("outputs/review/veg_sample.csv", index=False, encoding="utf-8")
T = 240
for k in range(0, len(t), 20):
    sheet = Image.new("RGB", (T * 5, T * 4), (255, 255, 255))
    for j, r in enumerate(t.iloc[k:k + 20].itertuples()):
        im = Image.open(f"{ART}/views/{r.picture}_y{int(r.yaw)}.jpg").convert("RGB")
        h = r.y1 - r.y0; cx = (r.x0 + r.x1) / 2; s = h * 0.2 + (r.x1 - r.x0) * 2
        y0 = max(0, r.y0 - 0.05 * h); y1 = r.y0 + 0.5 * h
        c = im.crop((int(max(0, cx - s)), int(y0), int(min(1024, cx + s)), int(y1)))
        sc = min(T / c.width, (T - 14) / c.height); c = c.resize((max(1, int(c.width * sc)), max(1, int(c.height * sc))))
        tile = Image.new("RGB", (T, T), (255, 255, 255)); tile.paste(c, ((T - c.width) // 2, 14))
        ImageDraw.Draw(tile).text((3, 1), f"V{r.vno} veg {r.veg_share:.2f}", fill=(0, 0, 0))
        sheet.paste(tile, ((j % 5) * T, (j // 5) * T))
    sheet.save(f"outputs/review/veg_{k // 20 + 1}.jpg", quality=88)
print(len(t))
