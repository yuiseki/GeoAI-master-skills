"""Road surface material from a picture of the road, by zero-shot classification with OpenCLIP: asphalt, concrete,
sett (paving stones, cobbles) or unpaved (gravel, dirt). Compared against OpenStreetMap's surface tag where the
road has one.

    uvx --with numpy --with pillow --with torch --with open_clip_torch python surface_material.py VIEWS_DIR OUT.csv \
        [--device cuda] [--top 0.55 --bottom 0.9 --left 0.3 --right 0.7]

Each view is cropped to the road ahead (fractions of its width and height) and compared with a few text prompts
per class; a class's score is the highest similarity among its prompts, turned into probabilities with a softmax
over classes (temperature 0.01, as CLIP's logit scale of 100). Zero-shot: nothing is trained on this area. The
accuracy has to be measured against labels (agreement()), and only the labelled rows count.
"""

import argparse
import csv
import json
import os
import sys

import numpy as np

CLASSES = ["asphalt", "concrete", "sett", "unpaved"]
PROMPTS = {
    "asphalt": ["a photo of an asphalt road surface", "a photo of a road paved with black asphalt"],
    "concrete": ["a photo of a concrete road surface", "a photo of a road made of concrete slabs"],
    "sett": ["a photo of a cobblestone road surface", "a photo of a road paved with stone setts or paving stones"],
    "unpaved": ["a photo of a gravel road", "a photo of an unpaved dirt road"],
}
OSM = {"asphalt": "asphalt", "concrete": "concrete", "concrete:plates": "concrete", "concrete:lanes": "concrete",
       "paving_stones": "sett", "sett": "sett", "cobblestone": "sett", "unhewn_cobblestone": "sett",
       "gravel": "unpaved", "fine_gravel": "unpaved", "compacted": "unpaved", "dirt": "unpaved", "ground": "unpaved",
       "unpaved": "unpaved", "earth": "unpaved", "sand": "unpaved", "grass": "unpaved"}


def osm_class(value):
    return OSM.get(value) if value else None


def classify(sims, names, temperature=0.01):
    """sims: pictures x prompts cosine similarities; names: the class of each prompt."""
    sims = np.asarray(sims, float)
    best = np.stack([sims[:, [i for i, n in enumerate(names) if n == c]].max(axis=1) for c in CLASSES], axis=1)
    z = best / temperature
    p = np.exp(z - z.max(axis=1, keepdims=True))
    p /= p.sum(axis=1, keepdims=True)
    return [CLASSES[i] for i in p.argmax(axis=1)], p


def agreement(pred, ref):
    pairs = [(p, r) for p, r in zip(pred, ref) if r is not None]
    conf = {}
    for p, r in pairs:
        conf.setdefault(r, {}).setdefault(p, 0)
        conf[r][p] += 1
    agree = sum(p == r for p, r in pairs)
    return {"labelled": len(pairs), "agree": agree, "accuracy": agree / len(pairs) if pairs else None,
            "confusion": conf}


def similarities(images, device="cpu"):
    import open_clip
    import torch
    model, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k", device=device)
    tok = open_clip.get_tokenizer("ViT-B-32")
    names = [c for c in CLASSES for _ in PROMPTS[c]]
    texts = [t for c in CLASSES for t in PROMPTS[c]]
    with torch.no_grad():
        te = model.encode_text(tok(texts).to(device))
        te = te / te.norm(dim=-1, keepdim=True)
        out = []
        for i in range(0, len(images), 64):
            x = torch.stack([pre(im) for im in images[i:i + 64]]).to(device)
            e = model.encode_image(x)
            e = e / e.norm(dim=-1, keepdim=True)
            out.append((e @ te.T).float().cpu().numpy())
    return np.concatenate(out), names


def main(argv=None):
    from PIL import Image
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("views")
    a.add_argument("out")
    a.add_argument("--device", default="cpu")
    a.add_argument("--top", type=float, default=0.55)
    a.add_argument("--bottom", type=float, default=0.9)
    a.add_argument("--left", type=float, default=0.3)
    a.add_argument("--right", type=float, default=0.7)
    a = a.parse_args(argv)
    files = sorted(f for f in os.listdir(a.views) if f.lower().endswith((".jpg", ".png")))
    crops = []
    for f in files:
        im = Image.open(os.path.join(a.views, f)).convert("RGB")
        w, h = im.size
        crops.append(im.crop((int(a.left * w), int(a.top * h), int(a.right * w), int(a.bottom * h))))
    sims, names = similarities(crops, a.device)
    labels, probs = classify(sims, names)
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["view", "surface"] + [f"p_{c}" for c in CLASSES])
        for f, l, p in zip(files, labels, probs):
            w.writerow([f, l] + [f"{v:.4f}" for v in p])
    print(json.dumps({"views": len(files)}))


if __name__ == "__main__":
    sys.exit(main())
