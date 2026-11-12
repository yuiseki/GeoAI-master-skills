import pandas as pd, numpy as np
from PIL import Image, ImageDraw
ART = "/work/artifacts/paris11-street-imagery"; OUT = "outputs/review"
s = pd.read_csv(f"{OUT}/road_sample.csv"); pt = pd.read_csv("outputs/06_damage_patches.csv")
TW, TH = 384, 288
for k in range(0, 40, 12):
    sheet = Image.new("RGB", (TW * 4, TH * 3), (255, 255, 255))
    for j, r in enumerate(s.iloc[k:k + 12].itertuples()):
        im = Image.open(f"{ART}/road/{r.picture}.jpg").convert("RGB"); d = ImageDraw.Draw(im)
        g = pt[pt.picture == r.picture]
        for q in g.itertuples():
            col = (255, 0, 0) if q.p_damage >= .5 else (0, 200, 0)
            d.rectangle([q.x, q.y, q.x + 112, q.y + 112], outline=col, width=2)
            d.text((q.x + 4, q.y + 4), f"{q.p_damage:.2f}", fill=col)
        d.text((6, 6), f"#{r.no}", fill=(255, 255, 0))
        sheet.paste(im.resize((TW, TH)), ((j % 4) * TW, (j // 4) * TH))
    sheet.save(f"{OUT}/road_{k // 12 + 1}.jpg", quality=90)
