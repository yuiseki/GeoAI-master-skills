"""Road surface damage from street-level pictures: a linear probe on image embeddings (OpenCLIP), trained on
labelled road-damage patches (RDD2022: D00 longitudinal crack, D10 transverse crack, D20 alligator crack, D40
pothole) and applied to patches of the road in perspective views.

    train:    uvx --with numpy --with pillow --with scikit-learn --with torch --with open_clip_torch \
                  python surface_damage.py train RDD_COUNTRY.zip OUTDIR [--device cuda]
    evaluate: uvx ... python surface_damage.py evaluate OUTDIR/probe.npz OTHER_COUNTRY.zip OUT.json
    predict:  uvx ... python surface_damage.py predict OUTDIR/probe.npz VIEWS_DIR OUT.csv [--top 0.5 --bottom 0.95]

Why patches: in RDD2022 the damage covers a small part of each picture. A probe on whole pictures can learn the
scene (country, road type, camera) instead of the cracks. Positive patches are the labelled boxes (with 15 %
margin); negative patches are squares of the lower road part of the same pictures that touch no box. The
evaluation splits by picture (5 folds), so no picture gives patches to both train and test.

What it is not: a pavement condition index measured in the field. The share of damaged patches is an image-based
indicator; turning it into a PCI needs distress type, severity and area per sample unit (ASTM D6433) and field
data to calibrate against, which this does not have.
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile

import numpy as np

MODEL = ("ViT-B-32", "laion2b_s34b_b79k")


def parse_voc(text):
    f = re.search(r"<filename>(.*?)</filename>", text).group(1)
    boxes = []
    for o in re.findall(r"<object>(.*?)</object>", text, re.S):
        n = re.search(r"<name>(.*?)</name>", o).group(1)
        b = [int(float(re.search(fr"<{k}>(.*?)</{k}>", o).group(1))) for k in ("xmin", "ymin", "xmax", "ymax")]
        boxes.append((n, tuple(b)))
    return f, boxes


def _overlaps(a, b):
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def negative_boxes(w, h, boxes, k, rng, top=0.5, bottom=0.92, tries=200):
    """k squares in the road part (rows top..bottom of the height) that overlap no labelled box."""
    out = []
    for _ in range(tries):
        if len(out) == k:
            break
        s = int(rng.integers(int(0.15 * w), int(0.3 * w)))
        x0 = int(rng.integers(0, w - s))
        y0 = int(rng.integers(int(top * h), max(int(top * h) + 1, int(bottom * h) - s)))
        c = (x0, y0, x0 + s, y0 + s)
        if c[3] <= bottom * h and not any(_overlaps(c, b) for b in boxes):
            out.append(c)
    return out


def _crop(img, box, margin=0.15, size=224):
    x0, y0, x1, y1 = box
    mx, my = (x1 - x0) * margin, (y1 - y0) * margin
    side = max(x1 - x0 + 2 * mx, y1 - y0 + 2 * my)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return img.crop((int(cx - side / 2), int(cy - side / 2), int(cx + side / 2), int(cy + side / 2))).resize((size, size))


def rdd_patches(zip_path, neg_per_image=2, seed=0):
    """Patches of every annotated picture: one per labelled box (damage) and neg_per_image without damage."""
    from PIL import Image
    rng = np.random.default_rng(seed)
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        for x in sorted(n for n in names if n.endswith(".xml") and "/annotations/" in n):
            f, boxes = parse_voc(z.read(x).decode("utf-8", "replace"))
            img_name = x.split("/annotations/")[0] + "/images/" + f
            if img_name not in names:
                continue
            img = Image.open(io.BytesIO(z.read(img_name))).convert("RGB")
            w, h = img.size
            for n, b in boxes:
                yield {"image": f, "damage": 1, "classes": n, "patch": _crop(img, b)}
            for b in negative_boxes(w, h, [b for _, b in boxes], neg_per_image, rng):
                yield {"image": f, "damage": 0, "classes": "", "patch": _crop(img, b, margin=0.0)}


def embed(patches, device="cpu", batch=64):
    import open_clip
    import torch
    model, _, pre = open_clip.create_model_and_transforms(MODEL[0], pretrained=MODEL[1], device=device)
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(patches), batch):
            x = torch.stack([pre(p) for p in patches[i:i + batch]]).to(device)
            e = model.encode_image(x)
            out.append((e / e.norm(dim=-1, keepdim=True)).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 512))


def fit_probe(emb, y, groups, path, C=1.0):
    """Logistic regression; 5-fold evaluation grouped by picture, then a fit on all and saved to path."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import GroupKFold
    oof = np.zeros(len(y))
    overlap = 0
    for tr, te in GroupKFold(5).split(emb, y, groups):
        overlap += len(set(groups[tr]) & set(groups[te]))
        m = LogisticRegression(C=C, max_iter=2000).fit(emb[tr], y[tr])
        oof[te] = m.predict_proba(emb[te])[:, 1]
    m = LogisticRegression(C=C, max_iter=2000).fit(emb, y)
    np.savez(path, coef=m.coef_[0], intercept=m.intercept_[0], model=np.array(list(MODEL)))
    pred = oof >= 0.5
    return {"auc": float(roc_auc_score(y, oof)), "average_precision": float(average_precision_score(y, oof)),
            "precision_at_0.5": float((y[pred] == 1).mean()) if pred.any() else None,
            "recall_at_0.5": float(pred[y == 1].mean()), "patches": int(len(y)), "positives": int(y.sum()),
            "pictures": int(len(set(groups))), "folds": 5, "test_images_overlap_train": int(overlap),
            "oof": oof}


def predict(emb, path):
    p = np.load(path)
    return 1 / (1 + np.exp(-(emb @ p["coef"] + float(p["intercept"]))))


def score(emb, y, path):
    """A saved probe on labelled patches it was not fitted on (another country, another camera)."""
    from sklearn.metrics import average_precision_score, roc_auc_score
    p = predict(emb, path)
    pred = p >= 0.5
    return {"auc": float(roc_auc_score(y, p)), "average_precision": float(average_precision_score(y, p)),
            "precision_at_0.5": float((y[pred] == 1).mean()) if pred.any() else None,
            "recall_at_0.5": float(pred[y == 1].mean()), "patches": int(len(y)), "positives": int(y.sum())}


def grid_patches(size, top=0.5, bottom=0.95, patch=None):
    """Square patches (side patch, default a fifth of the width) tiling rows top..bottom of a view (fractions of
    its height)."""
    w, h = size
    s = patch or int(0.2 * w)
    out = []
    y = int(top * h)
    while y + s <= int(bottom * h):
        x = 0
        while x + s <= w:
            out.append((x, y, x + s, y + s))
            x += s
        y += s
    return out


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = a.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("zip")
    t.add_argument("outdir")
    t.add_argument("--device", default="cpu")
    t.add_argument("--neg-per-image", type=int, default=2)
    e = sub.add_parser("evaluate")
    e.add_argument("probe")
    e.add_argument("zip")
    e.add_argument("out")
    e.add_argument("--device", default="cpu")
    e.add_argument("--neg-per-image", type=int, default=2)
    p = sub.add_parser("predict")
    p.add_argument("probe")
    p.add_argument("views")
    p.add_argument("out")
    p.add_argument("--device", default="cpu")
    p.add_argument("--top", type=float, default=0.5)
    p.add_argument("--bottom", type=float, default=0.95)
    p.add_argument("--patch", type=int, default=160)
    a = a.parse_args(argv)
    if a.cmd == "train":
        os.makedirs(a.outdir, exist_ok=True)
        rows = list(rdd_patches(a.zip, a.neg_per_image))
        emb = embed([r["patch"] for r in rows], a.device)
        y = np.array([r["damage"] for r in rows])
        g = np.array([r["image"] for r in rows])
        res = fit_probe(emb, y, g, os.path.join(a.outdir, "probe.npz"))
        oof = res.pop("oof")
        by = {}
        for r, o in zip(rows, oof):
            for c in (r["classes"] or "none").split(";"):
                by.setdefault(c, []).append(o)
        res["mean_oof_by_class"] = {k: float(np.mean(v)) for k, v in sorted(by.items())}
        res["zip"] = a.zip
        res["model"] = list(MODEL)
        with open(os.path.join(a.outdir, "train.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
        print(json.dumps(res))
    elif a.cmd == "evaluate":
        rows = list(rdd_patches(a.zip, a.neg_per_image))
        emb = embed([r["patch"] for r in rows], a.device)
        y = np.array([r["damage"] for r in rows])
        res = score(emb, y, a.probe)
        res.update(zip=a.zip, probe=a.probe, pictures=len({r["image"] for r in rows}))
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
        print(json.dumps(res))
    else:
        from PIL import Image
        files = sorted(f for f in os.listdir(a.views) if f.lower().endswith((".jpg", ".png")))
        patches, meta = [], []
        for f in files:
            img = Image.open(os.path.join(a.views, f)).convert("RGB")
            for b in grid_patches(img.size, a.top, a.bottom, a.patch):
                patches.append(img.crop(b).resize((224, 224)))
                meta.append((f, *b))
        prob = predict(embed(patches, a.device), a.probe)
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["view", "x0", "y0", "x1", "y1", "p_damage"])
            for m, pr in zip(meta, prob):
                w.writerow([*m, f"{pr:.4f}"])
        print(json.dumps({"views": len(files), "patches": len(patches)}))


if __name__ == "__main__":
    sys.exit(main())
