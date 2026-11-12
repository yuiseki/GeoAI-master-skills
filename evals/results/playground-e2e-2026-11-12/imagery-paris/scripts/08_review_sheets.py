"""Contact sheets for the visual check. Sample drawn with a fixed seed BEFORE looking: 40 pole detections uniformly
from poles.csv (all pole-like boxes, any score), 40 pictures uniformly from the 200 for the road. Sheets + a blank
labels CSV are written; labels are filled in by the reviewer (AI, stated in the report)."""
import csv, os, sys
import numpy as np, pandas as pd
from PIL import Image, ImageDraw
ART = "/work/artifacts/paris11-street-imagery"; OUT = "outputs/review"; os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(20261112)
poles = pd.read_csv(f"{ART}/poles/poles.csv")
idx = rng.choice(len(poles), size=min(40, len(poles)), replace=False)
s = poles.iloc[sorted(idx)].reset_index(drop=True); s.insert(0, "no", range(1, len(s) + 1))
s.to_csv(f"{OUT}/pole_sample.csv", index=False, encoding="utf-8")
TW, TH = 240, 360
def tile(r):
    im = Image.open(f"{ART}/views/{r.picture}_y{int(r.yaw)}.jpg").convert("RGB")
    h = r.y1 - r.y0; cx = (r.x0 + r.x1) / 2
    x0, x1 = cx - h * 0.33, cx + h * 0.33; y0, y1 = r.y0 - 0.05 * h, r.y1 + 0.05 * h
    c = im.crop((int(x0), int(y0), int(x1), int(y1)))
    sc = min(TW / c.width, (TH - 28) / c.height); c = c.resize((max(1, int(c.width * sc)), max(1, int(c.height * sc))))
    t = Image.new("RGB", (TW, TH), (255, 255, 255)); t.paste(c, ((TW - c.width) // 2, 28))
    d = ImageDraw.Draw(t)
    # box outline
    bx0 = (r.x0 - x0) * sc + (TW - c.width) // 2; bx1 = (r.x1 - x0) * sc + (TW - c.width) // 2
    by0 = (r.y0 - y0) * sc + 28; by1 = (r.y1 - y0) * sc + 28
    d.rectangle([bx0, by0, bx1, by1], outline=(255, 0, 0), width=1)
    lean = "NA" if pd.isna(r.lean_deg) else f"{r.lean_deg:+.1f}"
    d.text((3, 2), f"#{r.no} lean {lean} ({'c' if r.corrected else 'u'}) veg {r.veg_share:.2f}", fill=(0, 0, 0))
    d.text((3, 14), f"h={int(h)}px score {r.score:.2f}", fill=(0, 0, 0))
    return t
for k in range(0, len(s), 10):
    sheet = Image.new("RGB", (TW * 5, TH * 2), (255, 255, 255))
    for j, r in enumerate(s.iloc[k:k + 10].itertuples()):
        sheet.paste(tile(r), ((j % 5) * TW, (j // 5) * TH))
    sheet.save(f"{OUT}/poles_{k // 10 + 1}.jpg", quality=90)
# road
man = pd.read_csv(f"{ART}/manifest.csv"); pic = man.id.sample(40, random_state=20261112).tolist()
pd.DataFrame({"no": range(1, 41), "picture": pic}).to_csv(f"{OUT}/road_sample.csv", index=False, encoding="utf-8")
