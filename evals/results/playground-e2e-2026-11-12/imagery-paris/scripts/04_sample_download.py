"""Uniform sample (seed 0) of the eligible pictures (immergis / imajbox 360 HD, fov 360) listed in Paris 11e;
download hd, keep a 4096x2048 copy (1:1 for a 1024-px 90-degree view)."""
import sys, csv, json, os, hashlib
sys.path.insert(0, "/work/.agents/skills/street-imagery-inspection/scripts")
import panoramax_fetch as pf
import pandas as pd
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
ART = "/work/artifacts/paris11-street-imagery"
N, SEED = 200, 0
d = pd.read_csv(f"{ART}/listed.csv")
rows = d.to_dict("records")
kept, audit = pf.sample(rows, N, SEED, producer="immergis", fov=360)
# the camera must also be the 360 HD (immergis has a forward 3TX+ with fov 95, removed by fov filter already)
assert all(r["camera"] == "imajbox 360 HD" for r in kept)
os.makedirs(f"{ART}/images", exist_ok=True)
out = []
for i, r in enumerate(kept):
    p = f"{ART}/images/{r['id']}.jpg"
    if not os.path.exists(p):
        raw = f"{ART}/images/{r['id']}.hd.tmp"
        sha = pf.download(r["hd"], raw)
        im = Image.open(raw).convert("RGB"); r["hd_size"] = "x".join(map(str, im.size))
        im.resize((4096, 2048), Image.LANCZOS).save(p, quality=92); os.remove(raw)
        r["sha256_hd"] = sha
    else:
        r["hd_size"] = "cached"; r["sha256_hd"] = ""
    r["file"] = f"images/{r['id']}.jpg"
    out.append(r)
    if i % 20 == 0: print(i, flush=True)
cols = ["id","collection","lon","lat","datetime","azimuth","producer","camera","fov","licence","annotations","file","hd_size","sha256_hd","hd"]
with open(f"{ART}/manifest.csv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(sorted(out,key=lambda r:r["id"]))
audit.update(seed=SEED, n=N, producer="immergis", camera="imajbox 360 HD", listed_date="2026-11-12")
json.dump(audit, open("outputs/04_sample_audit.json","w",encoding="utf-8"), indent=1)
print(audit)
