"""Properties of the raw stacks that the change test assumes (read before the plan was fixed; no change test is run).

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with numpy --with scipy --with scikit-image python scripts/03_quality.py

Writes outputs/quality.json:
- enl_spatial: per orbit and date, the ENL by moments in 10 x 10 blocks of VV and VH over flat open land outside the
  outlines (WorldCover 30 grassland or 40 cropland, DEM < 10 m, at least 300 m from every outline): median and 90th percentile
- enl_ratio: the L that matches the median block variance of ln(X/Y) for two consecutive dates over the same blocks
  (var = 2 trigamma(L) for independent gamma speckle; texture that does not change between the dates cancels, a real
  change between them makes L smaller)
- corr_h, corr_v: correlation of ln(X/Y) between horizontal and vertical neighbours inside the blocks, after removing each
  block's mean (speckle correlation between pixels; a real change shared by the block is removed)
- coreg: per date, the shift (rows, cols) of the VV dB image against the orbit's temporal median, by phase correlation
  (upsampled 20 times) over the whole box
"""
import json
from pathlib import Path

import numpy as np
from scipy import ndimage, special
from scipy.optimize import brentq
from skimage.registration import phase_cross_correlation

from cp import local_enl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_flood/kita-inbanuma-sar-changepoint"
WIN = 10


def l_from_logratio_var(v):
    """L such that var(ln X - ln Y) = 2 trigamma(L) for independent gamma X, Y with L looks."""
    if not np.isfinite(v) or v <= 0:
        return float("nan")
    return brentq(lambda L: 2 * special.polygamma(1, L) - v, 0.2, 500)


def block_reduce(mask, win=WIN):
    r, c = (mask.shape[0] // win) * win, (mask.shape[1] // win) * win
    return mask[:r, :c].reshape(r // win, win, c // win, win).all(axis=(1, 3))


def main():
    aux = np.load(ART / "aux.npz")
    outlines = aux["ref_0922"] | aux["ref_0924"] | aux["ref_0925"] | aux["ref_1001"]
    far = ndimage.distance_transform_edt(~outlines) * 10 >= 300
    open_land = np.isin(aux["wc"], [30, 40]) & (aux["dem"] < 10) & far
    blocks = block_reduce(open_land)
    out = {"block": WIN, "open_land_pixels": int(open_land.sum()), "open_land_blocks": int(blocks.sum()),
           "orbits": {}}
    for o in (39, 141):
        st = np.load(ART / f"stack_o{o}.npy", mmap_mode="r")
        dates = [str(d) for d in aux[f"dates_o{o}"]]
        rows = []
        med = np.nanmedian(10 * np.log10(np.asarray(st[0])), axis=0)
        ref = np.nan_to_num(med - np.nanmean(med))
        for t, d in enumerate(dates):
            row = {"date": d}
            for k, pol in enumerate(("vv", "vh")):
                enl, _ = local_enl(np.asarray(st[k, t], float), WIN)
                e = enl[blocks & np.isfinite(enl)]
                row[f"enl_{pol}_median"] = round(float(np.median(e)), 3)
                row[f"enl_{pol}_p90"] = round(float(np.quantile(e, 0.9)), 3)
                if t > 0:
                    lr = np.log(np.asarray(st[k, t], float)) - np.log(np.asarray(st[k, t - 1], float))
                    r, c = blocks.shape[0] * WIN, blocks.shape[1] * WIN
                    b = lr[:r, :c].reshape(blocks.shape[0], WIN, blocks.shape[1], WIN).transpose(0, 2, 1, 3)
                    b = b.reshape(blocks.shape + (-1,))[blocks]
                    b = b[np.all(np.isfinite(b), axis=1)]
                    v = float(np.median(b.var(axis=1, ddof=1)))
                    row[f"enl_ratio_{pol}"] = round(l_from_logratio_var(v), 3)
                    m = np.zeros(lr.shape, bool)
                    m[:r, :c] = np.repeat(np.repeat(blocks, WIN, 0), WIN, 1)
                    x = np.where(m & np.isfinite(lr), lr, np.nan)
                    bm = np.nanmean(x[:r, :c].reshape(blocks.shape[0], WIN, blocks.shape[1], WIN), axis=(1, 3))
                    x[:r, :c] -= np.repeat(np.repeat(bm, WIN, 0), WIN, 1)  # remove each block's own change
                    def corr(a, b_):
                        ok = np.isfinite(a) & np.isfinite(b_)
                        return float(np.corrcoef(a[ok], b_[ok])[0, 1])
                    row[f"corr_h_{pol}"] = round(corr(x[:, :-1], x[:, 1:]), 3)
                    row[f"corr_v_{pol}"] = round(corr(x[:-1], x[1:]), 3)
            img = 10 * np.log10(np.asarray(st[0, t], float))
            img = np.nan_to_num(img - np.nanmean(img))
            shift, err, _ = phase_cross_correlation(ref, img, upsample_factor=20)
            row["coreg_shift_rows_cols"] = [round(float(s), 3) for s in shift]
            row["missing_vv"] = int(np.isnan(np.asarray(st[0, t])).sum())
            rows.append(row)
            print(o, row)
        out["orbits"][o] = rows
    (HERE.parent / "outputs/quality.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                                                     encoding="utf-8")


if __name__ == "__main__":
    main()
