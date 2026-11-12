"""A second, separate sample of 60 pole-like detections (different seed, none from the test 40) used only to choose
the pole verifier's threshold. Same tile layout as 08_review_sheets.py."""
import sys; sys.argv=[""]
import numpy as np, pandas as pd, re
src = open("scripts/08_review_sheets.py", encoding="utf-8").read()
# reuse tile() by exec'ing the definitions only
ns = {}
head = src.split("for k in range(0, len(s), 10):")[0]
head = head.replace('rng = np.random.default_rng(20261112)', 'rng = np.random.default_rng(7)').replace('size=min(40, len(poles))', 'size=len(poles)')
exec(head.replace('idx = rng.choice(len(poles), size=len(poles), replace=False)', 'test = pd.read_csv("outputs/review/pole_sample.csv"); idx = [i for i in rng.permutation(len(poles)) if not ((poles.picture[i]==test.picture)&(poles.yaw[i]==test.yaw)&(poles.x0[i]==test.x0)).any()][:60]').replace('s.to_csv(f"{OUT}/pole_sample.csv", index=False, encoding="utf-8")','s.to_csv(f"{OUT}/pole_dev_sample.csv", index=False, encoding="utf-8")'), ns)
s, tile = ns["s"], ns["tile"]
from PIL import Image
for k in range(0, 60, 10):
    sheet = Image.new("RGB", (240 * 5, 360 * 2), (255, 255, 255))
    for j, r in enumerate(s.iloc[k:k + 10].itertuples()):
        sheet.paste(tile(r), ((j % 5) * 240, (j // 5) * 360))
    sheet.save(f"outputs/review/dev_poles_{k // 10 + 1}.jpg", quality=88)
print(len(s))
