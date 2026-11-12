"""Road-surface damage indicator on the road ahead of the car (front view, pitch -15, fov 70, 1024x768): patches of
112 px tiling rows 0.40-0.69 and columns 0.2-0.8 (above the hood); probe = OpenCLIP ViT-B-32 + logistic regression
trained on RDD2022 Czech (artifacts/.../probe/probe.npz). Writes per-patch and per-picture tables."""
import sys, csv, os
sys.path.insert(0, "/work/.agents/skills/street-imagery-inspection/scripts")
import numpy as np, torch
torch.set_num_threads(8)
from PIL import Image
import surface_damage as sd
from equirect_view import perspective
ART = "/work/artifacts/paris11-street-imagery"
os.makedirs(f"{ART}/road", exist_ok=True)
P = 112
man = list(csv.DictReader(open(f"{ART}/manifest.csv", encoding="utf-8")))
patches, meta = [], []
for m in man:
    vp = f"{ART}/road/{m['id']}.jpg"
    if not os.path.exists(vp):
        pano = np.asarray(Image.open(f"{ART}/{m['file']}").convert("RGB"))
        Image.fromarray(perspective(pano, 0, -15.0, 70, (1024, 768))).save(vp, quality=92)
    img = Image.open(vp).convert("RGB")
    y = int(0.40 * 768)
    while y + P <= int(0.69 * 768):
        x = int(0.2 * 1024)
        while x + P <= int(0.8 * 1024):
            patches.append(img.crop((x, y, x + P, y + P)).resize((224, 224))); meta.append((m["id"], x, y)); x += P
        y += P
print(len(patches), "patches", len(man), "pictures", flush=True)
prob = sd.predict(sd.embed(patches), f"{ART}/probe/probe.npz")
with open("outputs/06_damage_patches.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["picture", "x", "y", "p_damage"])
    for (i, x, y), p in zip(meta, prob): w.writerow([i, x, y, round(float(p), 4)])
import pandas as pd
d = pd.read_csv("outputs/06_damage_patches.csv")
g = d.groupby("picture").p_damage.agg(n_patches="size", mean_p="mean", max_p="max", share_damaged=lambda s: (s >= .5).mean()).reset_index()
g.to_csv("outputs/06_damage_pictures.csv", index=False, encoding="utf-8")
print(g.describe().to_string())
