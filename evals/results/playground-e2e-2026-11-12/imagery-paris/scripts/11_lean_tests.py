"""Check lean_grad on drawn poles of known tilt (sign, bias, noise, width) before using it on real boxes."""
import numpy as np, json
from PIL import Image, ImageDraw, ImageFilter
from leangrad import lean_grad
rng = np.random.default_rng(0); rows = []
for tilt in (-6, -3, -1, 0, 1, 3, 6):
    for wpx, con in ((5, 100), (8, 100), (14, 100), (5, 25), (8, 25), (14, 25)):
        errs = []
        for k in range(20):
            bg = rng.normal(150, 25, (1024, 1024)); bg = np.array(Image.fromarray(bg.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), float)
            im = Image.fromarray(bg.astype(np.uint8)); d = ImageDraw.Draw(im)
            cx, y_top, y_bot = rng.integers(300, 700), 300, 900
            dx = np.tan(np.radians(tilt)) * (y_bot - y_top)   # top displaced to the right when tilt > 0
            d.line([(cx + dx / 2, y_top), (cx - dx / 2, y_bot)], fill=int(150 + rng.choice([-1, 1]) * con), width=wpx)
            g = np.array(im.filter(ImageFilter.GaussianBlur(1)), float) + rng.normal(0, 4, (1024, 1024))
            est = lean_grad(g, (cx - 40 - abs(dx) / 2, y_top, cx + 40 + abs(dx) / 2, y_bot))
            errs.append(np.nan if est is None else est - tilt)
        e = np.array(errs); rows.append({"tilt": tilt, "width_px": wpx, "contrast": con, "bias": float(np.nanmean(e)), "sd": float(np.nanstd(e)), "failed": int(np.isnan(e).sum())})
import pandas as pd
t = pd.DataFrame(rows); t.to_csv("outputs/11_lean_synthetic.csv", index=False, encoding="utf-8")
print(t.to_string()); print("max |bias|", t.bias.abs().max(), "max sd", t.sd.max())
