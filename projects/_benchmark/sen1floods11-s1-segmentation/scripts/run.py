"""Data, models, training and evaluation of EXPERIMENT_PLAN.md.

  python3 scripts/run.py otsu                                  # B0: the authors' Otsu labels, both IoU counts
  python3 scripts/run.py train --model fcn|unet --seed S [--epochs 100] [--accum 1] [--device cuda]
  python3 scripts/run.py summary                               # every run: test and Bolivia, chip mean and pooled

Per-chip IoU of every run goes to outputs/chips_<model>_s<seed>.csv; predictions to artifacts.
"""

import argparse
import csv
import json
import math
import time
from pathlib import Path

import numpy as np

from s1f11 import IGNORE, chip_iou, flood_permanent, labels_to_target, pooled_iou, preprocess, random_crop_flip, tiles4, untile4

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / "artifacts/_benchmark/sen1floods11-s1-segmentation"
RAW = ART / "raw"
OUT = Path(__file__).resolve().parent.parent / "outputs"
SPLITS = ("train", "valid", "test", "bolivia")


def read(path):
    import rasterio
    with rasterio.open(path) as r:
        return r.read()


def chips(split):
    with open(RAW / f"flood_{split}_data.csv", encoding="utf-8") as f:
        return [row[0].replace("_S1Hand.tif", "") for row in csv.reader(f) if row]


def load(split):
    out = []
    for c in chips(split):
        x = preprocess(read(RAW / "S1Hand" / f"{c}_S1Hand.tif"))
        y = labels_to_target(read(RAW / "LabelHand" / f"{c}_LabelHand.tif")[0])
        jrc = read(RAW / "JRCWaterHand" / f"{c}_JRCWaterHand.tif")[0]
        out.append(dict(chip=c, event=c.split("_")[0], x=x, y=y, jrc=jrc))
    return out


def scores(pred, d):
    (pf, tf), (pp, tp) = flood_permanent(pred, d["y"], d["jrc"])
    return dict(aw=chip_iou(pred, d["y"]), fw=chip_iou(pf, tf), pw=chip_iou(pp, tp))


def otsu():
    rows = []
    for split in ("test", "bolivia"):
        data = load(split)
        preds = [(read(RAW / "S1OtsuLabelHand" / f"{d['chip']}_S1OtsuLabelHand.tif")[0] == 1).astype("int64") for d in data]
        s = [scores(p, d) for p, d in zip(preds, data)]
        rows.append(dict(split=split, chips=len(data), aw_chip_mean=round(np.mean([v["aw"] for v in s]), 4),
                         fw_chip_mean=round(np.mean([v["fw"] for v in s]), 4),
                         pw_chip_mean=round(np.mean([v["pw"] for v in s]), 4),
                         aw_pooled=round(pooled_iou(preds, [d["y"] for d in data]), 4)))
        write_chips(f"otsu", split, data, s)
        print(rows[-1], flush=True)
    with open(OUT / "b0_otsu.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(OUT / "split_counts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["split", "chips", "events"])
        for s in SPLITS:
            c = chips(s)
            w.writerow([s, len(c), len({x.split("_")[0] for x in c})])


def write_chips(tag, split, data, s):
    path = OUT / f"chips_{tag}.csv"
    new = not path.exists() or split == "test"
    with open(path, "w" if new else "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["split", "chip", "event", "aw", "fw", "pw"])
        for d, v in zip(data, s):
            w.writerow([split, d["chip"], d["event"], round(v["aw"], 6), round(v["fw"], 6), round(v["pw"], 6)])


def to_gn(module, groups=16):
    import torch.nn as nn
    for name, child in module.named_children():
        if isinstance(child, nn.BatchNorm2d):
            setattr(module, name, nn.GroupNorm(groups, child.num_features, eps=child.eps, affine=child.affine))
        else:
            to_gn(child, groups)
    return module


def build(model):
    import torch.nn as nn
    if model == "fcn":
        from torchvision.models.segmentation import fcn_resnet50
        net = fcn_resnet50(weights=None, weights_backbone=None, num_classes=2)
        net.backbone.conv1 = nn.Conv2d(2, 64, kernel_size=7, stride=2, padding=3, bias=False)
        return to_gn(net), lambda o: o["out"]
    if model == "unet":
        import segmentation_models_pytorch as smp
        net = smp.Unet("resnet34", encoder_weights=None, in_channels=2, classes=2)
        return to_gn(net), lambda o: o
    raise ValueError(model)


def predict(net, head, data, device, bs=4):
    import torch
    preds = []
    net.eval()
    with torch.no_grad():
        for i in range(0, len(data), bs):
            x = np.concatenate([tiles4(d["x"]) for d in data[i:i + bs]])             # (4 * b, 2, 256, 256)
            o = head(net(torch.from_numpy(x).to(device))).argmax(1).cpu().numpy()
            for k in range(len(data[i:i + bs])):
                preds.append(untile4(o[4 * k:4 * k + 4]))
    net.train()
    return preds


def train(a):
    import torch
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    device = a.device
    tr, va = load("train"), load("valid")
    net, head = build(a.model)
    net.to(device)
    crit = torch.nn.CrossEntropyLoss(weight=torch.tensor([1.0, 8.0], device=device), ignore_index=IGNORE)
    opt = torch.optim.AdamW(net.parameters(), lr=5e-4)
    steps = math.ceil(len(tr) / 16)
    sched = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(opt, steps * 10, T_mult=2, eta_min=0)
    tag = f"{a.model}_s{a.seed}"
    log = open(OUT / f"train_{tag}.csv", "w", newline="", encoding="utf-8")
    w = csv.writer(log)
    w.writerow(["epoch", "seconds", "train_loss", "valid_chip_mean_iou"])
    best, t0 = -1.0, time.time()
    mb = 16 // a.accum
    for ep in range(1, a.epochs + 1):
        order = rng.permutation(len(tr))
        losses = []
        for s in range(steps):
            idx = order[s * 16:(s + 1) * 16]
            opt.zero_grad()
            for k in range(0, len(idx), mb):
                pairs = [random_crop_flip(tr[i]["x"], tr[i]["y"], 256, rng) for i in idx[k:k + mb]]
                x = torch.from_numpy(np.stack([p[0] for p in pairs])).to(device)
                y = torch.from_numpy(np.stack([p[1] for p in pairs])).to(device)
                loss = crit(head(net(x)), y) * len(pairs) / len(idx)
                loss.backward()
                losses.append(loss.item() * len(idx) / len(pairs))
            opt.step()
            sched.step()
        v = float(np.mean([chip_iou(p, d["y"]) for p, d in zip(predict(net, head, va, device), va)]))
        w.writerow([ep, round(time.time() - t0), round(float(np.mean(losses)), 4), round(v, 4)])
        log.flush()
        print(f"{tag} epoch {ep} {time.time() - t0:.0f}s loss {np.mean(losses):.4f} valid {v:.4f}", flush=True)
        if v > best:
            best = v
            torch.save(net.state_dict(), ART / f"model_{tag}.pt")
    # evaluate the best epoch on test and Bolivia
    net.load_state_dict(torch.load(ART / f"model_{tag}.pt", map_location=device))
    for split in ("test", "bolivia"):
        data = load(split)
        preds = predict(net, head, data, device)
        np.save(ART / f"pred_{tag}_{split}.npy", np.stack(preds).astype("uint8"))
        write_chips(tag, split, data, [scores(p, d) for p, d in zip(preds, data)])
    json.dump(dict(model=a.model, seed=a.seed, epochs=a.epochs, accum=a.accum, best_valid=best,
                   seconds=round(time.time() - t0), device=device, torch=torch.__version__),
              open(OUT / f"train_{tag}.json", "w", encoding="utf-8"), indent=1)


def boot(x, groups, reps=2000, seed=0):
    rng = np.random.default_rng(seed)
    g = np.unique(groups, return_inverse=True)[1]
    sums, cnt = np.bincount(g, x), np.bincount(g)
    idx = rng.integers(0, len(sums), (reps, len(sums)))
    return np.percentile(sums[idx].sum(1) / cnt[idx].sum(1), [2.5, 97.5])


def summary(a):
    rows = []
    for path in sorted(OUT.glob("chips_*.csv")):
        tag = path.stem.replace("chips_", "")
        r = list(csv.DictReader(open(path, encoding="utf-8")))
        for split in ("test", "bolivia"):
            s = [x for x in r if x["split"] == split]
            aw = np.array([float(x["aw"]) for x in s])
            lo, hi = boot(aw, np.arange(len(aw)))
            elo, ehi = boot(aw, [x["event"] for x in s])
            preds = None
            pooled = ""
            pf = ART / f"pred_{tag}_{split}.npy"
            if pf.exists():
                data = load(split)
                pooled = round(pooled_iou(list(np.load(pf)), [d["y"] for d in data]), 4)
            rows.append(dict(model=tag, split=split, chips=len(s), aw=round(aw.mean(), 4),
                             fw=round(np.mean([float(x["fw"]) for x in s]), 4),
                             pw=round(np.mean([float(x["pw"]) for x in s]), 4),
                             ci_chip_low=round(lo, 4), ci_chip_high=round(hi, 4),
                             ci_event_low=round(elo, 4), ci_event_high=round(ehi, 4), aw_pooled=pooled))
            print(rows[-1], flush=True)
    with open(OUT / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--model", default="fcn")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--accum", type=int, default=1)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    {"otsu": lambda: otsu(), "train": lambda: train(a), "summary": lambda: summary(a)}[a.cmd]()


if __name__ == "__main__":
    main()
