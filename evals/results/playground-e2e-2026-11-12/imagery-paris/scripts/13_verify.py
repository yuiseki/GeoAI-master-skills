"""Zero-shot OpenCLIP verifier: is a pole-like box a pole? Threshold chosen on the dev 60, scored on the test 40
(labels by AI review, see report). Writes outputs/13_poles_verified.csv (all 922 boxes) and outputs/13_verifier.json."""
import sys, json
sys.path.insert(0, "/work/.agents/skills/street-imagery-inspection/scripts")
import numpy as np, pandas as pd, torch, open_clip
from PIL import Image
from sklearn.metrics import roc_auc_score
torch.set_num_threads(8)
ART = "/work/artifacts/paris11-street-imagery"
poles = pd.read_csv(f"{ART}/poles/poles.csv").reset_index(drop=True)
model, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k"); model.eval()
tok = open_clip.get_tokenizer("ViT-B-32")
POS = ["a photo of a street lamp post", "a photo of a traffic light pole", "a photo of a metal pole on a sidewalk", "a photo of a signpost pole"]
NEG = ["a photo of a drainpipe on a building wall", "a photo of a building facade", "a photo of a tree trunk", "a photo of a wall corner"]
with torch.no_grad():
    t = model.encode_text(tok(POS + NEG)); t = t / t.norm(dim=-1, keepdim=True)
def crop(r):
    im = Image.open(f"{ART}/views/{r.picture}_y{int(r.yaw)}.jpg").convert("RGB")
    h = r.y1 - r.y0; cx = (r.x0 + r.x1) / 2; s = max(h * 0.35, (r.x1 - r.x0) * 3)
    return im.crop((int(max(0, cx - s)), int(max(0, r.y0)), int(min(1024, cx + s)), int(min(1024, r.y1)))).resize((224, 224))
emb = []
with torch.no_grad():
    for i in range(0, len(poles), 64):
        x = torch.stack([pre(crop(r)) for r in poles.iloc[i:i + 64].itertuples()])
        e = model.encode_image(x); emb.append((e / e.norm(dim=-1, keepdim=True)).numpy())
emb = np.concatenate(emb); sim = emb @ t.numpy().T * 100
lse = lambda a: np.log(np.exp(a).sum(1))
poles["verify"] = lse(sim[:, :len(POS)]) - lse(sim[:, len(POS):])
def lab(sample, labels):
    s = pd.read_csv(sample); l = pd.read_csv(labels)[["no", "is_pole"]]; s = s.merge(l, on="no")
    return s.merge(poles[["picture", "yaw", "x0", "verify"]], on=["picture", "yaw", "x0"], how="left")
test = lab("outputs/review/pole_sample.csv", "outputs/review/pole_labels_test.csv")
dev = lab("outputs/review/pole_dev_sample.csv", "outputs/review/pole_labels_dev.csv")
R = {"dev_n": len(dev), "dev_pole_share": float(dev.is_pole.mean()), "test_n": len(test), "test_pole_share": float(test.is_pole.mean())}
R["dev_auc_verify"] = roc_auc_score(dev.is_pole, dev.verify); R["dev_auc_detector_score"] = roc_auc_score(dev.is_pole, dev.score)
R["test_auc_verify"] = roc_auc_score(test.is_pole, test.verify); R["test_auc_detector_score"] = roc_auc_score(test.is_pole, test.score)
best = max(((2 * ((dev.verify >= th) & (dev.is_pole == 1)).sum() / (((dev.verify >= th).sum() + dev.is_pole.sum()) or 1)), th) for th in np.sort(dev.verify.unique()))
R["threshold_from_dev"], R["dev_f1_at_threshold"] = float(best[1]), float(best[0])
th = best[1]; pr = test.verify >= th
R["test_precision"] = float((test.is_pole[pr] == 1).mean()) if pr.any() else None
R["test_recall"] = float(pr[test.is_pole == 1].mean()); R["test_kept"] = int(pr.sum())
R["boxes_kept_all"] = int((poles.verify >= th).sum()); R["boxes_all"] = len(poles)
poles["verified"] = poles.verify >= th
poles.to_csv("outputs/13_poles_verified.csv", index=False, encoding="utf-8")
json.dump({k: (float(v) if isinstance(v, (np.floating,)) else v) for k, v in R.items()}, open("outputs/13_verifier.json", "w", encoding="utf-8"), indent=1)
print(json.dumps({k: (float(v) if isinstance(v, (np.floating,)) else v) for k, v in R.items()}, indent=1))
