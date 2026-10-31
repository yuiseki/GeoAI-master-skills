"""Run the planned detection on the analysis grid.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with shapely python scripts/03_detect.py

Reads artifacts/.../grid.npz, writes artifacts/.../detect_plan.npz (prob, zone, det_vv, det_vvvh) and
outputs/detect_fit.json (the fitted distributions, thresholds, the parts of sure water and their levels).
"""
import json
from pathlib import Path

import numpy as np

from sar import detect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/kita-inbanuma-sar-replication"


def load_grid():
    return dict(np.load(ART / "grid.npz"))


def run(g, **kw):
    return detect(g["vv_b"], g["vh_b"], g["vv_a"], g["vh_a"], g["dem"], g["water"], **kw)


def main():
    g = load_grid()
    r = run(g)
    np.savez_compressed(ART / "detect_plan.npz", prob=r["prob"].astype(np.float32), zone=r["zone"],
                        det_vv=r["det_vv"], det_vvvh=r["det_vvvh"], labels=r["labels"].astype(np.int32))
    sizes = np.bincount(r["labels"].ravel())[1:]
    lv = np.array([r["levels"][k] for k in sorted(r["levels"])])
    out = {"params": r["params"], "fit": {k: round(v, 3) if isinstance(v, float) else v for k, v in r["fit"].items()},
           "vh_threshold_db_article": -3.3,
           "parts": {"n": int(len(sizes)), "pixels_total": int(sizes.sum()),
                     "largest_pixels": [int(v) for v in np.sort(sizes)[::-1][:5]],
                     "level_m_of_largest": float(r["levels"][int(np.argmax(sizes)) + 1]) if len(sizes) else None,
                     "level_m_quantiles": [round(float(v), 2) for v in np.nanquantile(lv, [0, 0.25, 0.5, 0.75, 1])] if len(lv) else []},
           "zone_km2": round(float(r["zone"].sum()) * 100 / 1e6, 3),
           "det_vv_km2": round(float(r["det_vv"].sum()) * 100 / 1e6, 3),
           "det_vvvh_km2": round(float(r["det_vvvh"].sum()) * 100 / 1e6, 3)}
    (HERE.parent / "outputs/detect_fit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
