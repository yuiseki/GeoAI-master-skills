"""Exploratory (after the results): the 2019-10-13 flood extent of 大田区's own flood record map, against the SAR.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with pillow --with numpy --with duckdb==1.5.5 --with shapely --with pyproj --with scipy --with scikit-image --with rasterio python -u scripts/07_ota_map.py

Input: raw/docs/ota_shinsui_jisseki_s60-r7.pdf (大田区浸水実績図 昭和60年〜令和7年, A1, one 400 dpi JPEG inside; given by
the requester, 2026-11-03) and the 町丁 polygons of 大田区 from estat-boundary-2020 (HF yuiseki/estat-boundary-2020,
revision 823195c, raw/estat/parquet/r2ka13.parquet, JGD2000).

1. Georeference: the dark line work of the map (grey < 110) is matched to the 町丁 boundaries drawn in JGD2000 plane
   rectangular IX (EPSG:2451) at 2 m, by phase correlation, over scale 1.016 m/px x {0.998, 1, 1.002} and rotation
   {-0.1, 0, 0.1} degrees (a wider search at 4 m, 0.98 to 1.03 and -1 to 1 degrees, peaked at 1.016 m/px and 0
   degrees). The best score and the transform go to outputs/ota_map.json; artifacts/.../local_only/ota_map_overlay.png
   shows the 町丁 boundaries (red) over the map at 田園調布 to check it by eye. It is a crop of the ward's map, whose
   terms (https://www.city.ota.tokyo.jp/aboutweb/policy.html) forbid reuse without permission, so it stays out of the
   repository.
2. Mask of legend No. 22 (令和元年 10月13日 台風, 559 件): pixels within 22 (RGB distance) of the legend swatch colour
   and nearer to it than to any other swatch, outside the legend box, opened with a 5 x 5 window (a first run picked
   the brownish anti-aliased rims of orange fills under black text), closed with a 7 x 7 window (to bridge the street
   lines and the numbers printed over the fill), parts under 50 m2 dropped. The map fills blocks (街区) and leaves the
   streets white; a second extent closes the mask with a 25 x 25 window to take in the streets between filled blocks.
3. On the SAR grid (pixel centre in the mask): its area, its overlap with the REC pixels of 大田区, and the share of
   built-up pixels that brightened (+3 dB) or darkened (-3 dB) on 2019-10-13 (main settings) and on the placebo pair,
   inside the mask, inside the mask but outside REC, and in the rest of 大田区 on the grid.
"""
import json

import duckdb
import numpy as np
import shapely
from PIL import Image, ImageDraw
from pyproj import Transformer
from rasterio.features import rasterize, shapes
from rasterio.transform import Affine, from_origin
from scipy import ndimage
from skimage.registration import phase_cross_correlation
from skimage.transform import rescale, rotate

import flood
from common import ART, OUT, RAW, SCENES, UTM

Image.MAX_IMAGE_PIXELS = None
PDF = RAW / "docs/ota_shinsui_jisseki_s60-r7.pdf"
ESTAT = RAW / "estat/parquet/r2ka13.parquet"
SWATCHES = {1: (57, 178, 111), 2: (1, 159, 194), 3: (232, 79, 100), 4: (250, 191, 1), 5: (244, 163, 107),
            6: (0, 101, 155), 7: (186, 127, 181), 8: (196, 184, 0), 9: (192, 106, 55), 10: (112, 148, 120),
            11: (179, 73, 148), 12: (91, 78, 158), 13: (255, 228, 63), 14: (229, 0, 127), 15: (34, 173, 230),
            16: (1, 166, 90), 17: (231, 0, 19), 18: (0, 100, 40), 19: (122, 135, 45), 20: (238, 116, 67),
            21: (143, 111, 175), 22: (188, 138, 85), 23: (85, 126, 190), 24: (144, 191, 89), 25: (43, 182, 177),
            26: (243, 153, 57)}  # legend swatches, measured on the map (mean RGB of each swatch)
TARGET, TOL, OPEN, CLOSE, MIN_M2, CLOSE_STREETS = 22, 22.0, 5, 7, 50.0, 25
LEGEND = (430, 5500, 2700, 8950)  # map pixels (col0, row0, col1, row1) of the legend box, left out


def load_image():
    import io
    import pypdf
    page = pypdf.PdfReader(str(PDF)).pages[0]
    (img,) = page.images
    return Image.open(io.BytesIO(img.data)).convert("RGB")


def main():
    im = load_image()
    rgb = np.asarray(im)
    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial")
    rows = c.sql(f"select ST_AsWKB(ST_GeomFromWKB(geometry)), S_NAME from '{ESTAT}' where CITY_NAME = '大田区'").fetchall()
    gs = shapely.from_wkb([bytes(r[0]) for r in rows])
    t = Transformer.from_crs("EPSG:4612", "EPSG:2451", always_xy=True)
    gs = shapely.transform(gs, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))
    lines = shapely.union_all([g.boundary for g in gs])

    # 1. georeference
    R, pad = 2.0, 1500
    x0, y0, x1, y1 = lines.bounds
    W, H = int((x1 - x0 + 2 * pad) / R), int((y1 - y0 + 2 * pad) / R)
    ox, oy = x0 - pad, y1 + pad
    ref = rasterize([(lines.buffer(4), 1)], out_shape=(H, W), transform=from_origin(ox, oy, R, R), fill=0,
                    dtype="uint8").astype(np.float32)
    ref = ndimage.gaussian_filter(ref, 2)
    dark = (rgb.mean(2) < 110).astype(np.float32)
    best, tried = None, []
    for s in (0.998, 1.0, 1.002):
        mpp = 1.016 * s
        for rot in (-0.1, 0.0, 0.1):
            m = rescale(dark, mpp / R, anti_aliasing=True, preserve_range=True)
            if rot:
                m = rotate(m, rot, resize=False, preserve_range=True)
            m = ndimage.gaussian_filter(m, 2)
            Hc, Wc = max(H, m.shape[0]), max(W, m.shape[1])
            A = np.zeros((Hc, Wc), np.float32)
            A[:H, :W] = ref - ref.mean()
            B = np.zeros((Hc, Wc), np.float32)
            B[:m.shape[0], :m.shape[1]] = m - m.mean()
            sh, _, _ = phase_cross_correlation(A, B, upsample_factor=4, normalization=None)
            Bs = ndimage.shift(B, sh, order=1)
            score = float((A * Bs).sum() / np.sqrt((A * A).sum() * (Bs * Bs).sum()))
            tried.append([s, rot, round(score, 4)])
            print(s, rot, sh, round(score, 4), flush=True)
            if best is None or score > best[0]:
                best = (score, s, rot, [float(v) for v in sh])
    score, s, rot, sh = best
    if rot != 0:
        raise RuntimeError("best rotation is not 0; this script only handles an unrotated map")
    mpp = 1.016 * s
    X0, Y0 = ox + sh[1] * R, oy - sh[0] * R
    geo = Affine(mpp, 0, X0, 0, -mpp, Y0)  # map pixel (col, row) -> EPSG:2451

    crop = (480, 2160, 1440, 2880)
    sub = im.crop(crop)
    d = ImageDraw.Draw(sub)
    for g in gs:
        for p in getattr(g, "geoms", [g]):
            d.line([((X - X0) / mpp - crop[0], (Y0 - Y) / mpp - crop[1]) for X, Y in p.exterior.coords],
                   fill=(255, 0, 0), width=3)
    (ART / "local_only").mkdir(exist_ok=True)
    sub.save(ART / "local_only/ota_map_overlay.png")  # a crop of the ward's map: kept out of the repository (see report)

    # 2. mask of No. 22
    def dist(v):  # row block by row block, to keep the memory small
        out = np.empty(rgb.shape[:2], np.float32)
        for r0 in range(0, rgb.shape[0], 1000):
            b = rgb[r0:r0 + 1000].astype(np.float32) - np.array(v, np.float32)
            out[r0:r0 + 1000] = np.sqrt((b * b).sum(2))
        return out
    dt = dist(SWATCHES[TARGET])
    others = np.full(dt.shape, np.inf, np.float32)
    for k, v in SWATCHES.items():
        if k != TARGET:
            np.minimum(others, dist(v), out=others)
    mask = (dt < TOL) & (dt < others)
    del dt, others
    mask[LEGEND[1]:LEGEND[3], LEGEND[0]:LEGEND[2]] = False
    mask = ndimage.binary_opening(mask, structure=np.ones((OPEN, OPEN), bool))  # drops the anti-aliased rims of other fills
    mask = ndimage.binary_closing(mask, structure=np.ones((CLOSE, CLOSE), bool))
    lab, n = ndimage.label(mask)
    sizes = np.bincount(lab.ravel()) * mpp * mpp
    keep = sizes >= MIN_M2
    keep[0] = False
    mask = keep[lab]
    polys = [shapely.geometry.shape(gj) for gj, v in shapes(mask.astype(np.uint8), mask=mask, transform=geo) if v == 1]
    ext = shapely.union_all(polys)
    ms = ndimage.binary_closing(mask, structure=np.ones((CLOSE_STREETS, CLOSE_STREETS), bool))  # blocks and the streets between them
    ext_s = shapely.union_all([shapely.geometry.shape(gj) for gj, v in shapes(ms.astype(np.uint8), mask=ms, transform=geo) if v == 1])
    to_utm = Transformer.from_crs("EPSG:2451", UTM, always_xy=True)
    ext_utm = shapely.transform(ext, lambda xy: np.column_stack(to_utm.transform(xy[:, 0], xy[:, 1])))
    ext_s_utm = shapely.transform(ext_s, lambda xy: np.column_stack(to_utm.transform(xy[:, 0], xy[:, 1])))
    to_ll = Transformer.from_crs("EPSG:2451", "EPSG:4326", always_xy=True)
    ext_ll = shapely.transform(ext, lambda xy: np.column_stack(to_ll.transform(xy[:, 0], xy[:, 1])))
    (ART / "ota_2019_extent.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": shapely.geometry.mapping(ext_ll),
        "properties": {"derived": "traced by colour from 大田区浸水実績図 (legend No. 22, 令和元年10月13日); not an observation",
                       "script": "scripts/07_ota_map.py"}}]}) + "\n", encoding="utf-8")

    ext_s_ll = shapely.transform(ext_s, lambda xy: np.column_stack(to_ll.transform(xy[:, 0], xy[:, 1])))
    (ART / "ota_2019_extent_streets.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": shapely.geometry.mapping(ext_s_ll),
        "properties": {"derived": "ota_2019_extent closed with a 25 m window to take in the streets; not an observation",
                       "script": "scripts/07_ota_map.py"}}]}) + "\n", encoding="utf-8")

    # 3. against the SAR grid
    aux = dict(np.load(ART / "aux.npz"))
    tr = Affine(*aux["transform"][:6])
    shape = aux["wc"].shape
    m19 = rasterize([(ext_utm, 1)], out_shape=shape, transform=tr, fill=0, dtype="uint8").astype(bool)
    m19s = rasterize([(ext_s_utm, 1)], out_shape=shape, transform=tr, fill=0, dtype="uint8").astype(bool)
    ota = aux["ward"] == 13111
    rec = aux["rec"] & ota
    built = aux["wc"] == 50
    shift = json.loads((OUT / "grid_summary.json").read_text(encoding="utf-8"))["orbits"]["46"]["shift_back"]
    st = np.load(ART / "stack_o46.npy", mmap_mode="r")
    roles = [r for r, _ in SCENES[46]]
    pre = [i for i, r in enumerate(roles) if r == "pre"]
    ev = roles.index("event")

    def img(idx):
        a = np.asarray(st[0, idx], float)
        a = np.nanmean(a, axis=0) if a.ndim == 3 else a
        return flood.boxcar(flood.apply_int_shift(a, shift), 3)

    d_ev = flood.ratio_db(img(ev), img(pre))
    d_pl = flood.ratio_db(img(pre[-1]), img(pre[:-1]))
    ok = np.isfinite(d_ev) & np.isfinite(d_pl) & ota & (aux["wc"] != 80)

    def rates(sel):
        sel = sel & ok & built
        return {"built_pixels": int(sel.sum()),
                "bright": round(float((d_ev[sel] >= 3).mean()), 4) if sel.any() else None,
                "dark": round(float((d_ev[sel] <= -3).mean()), 4) if sel.any() else None,
                "bright_placebo": round(float((d_pl[sel] >= 3).mean()), 4) if sel.any() else None}

    out = {"note": "exploratory, after the results; the extent is traced from a map image, not an observation",
           "georef": {"crs": "EPSG:2451", "m_per_px": round(mpp, 5), "rotation_deg": rot, "X0": round(X0, 2),
                      "Y0": round(Y0, 2), "score": round(score, 4), "tried": tried},
           "mask": {"legend_no": TARGET, "swatch_rgb": SWATCHES[TARGET], "tol": TOL, "open_px": OPEN, "close_px": CLOSE, "legend_box_px": LEGEND,
                    "min_m2": MIN_M2, "parts": len(polys), "area_m2_jgd2000_ix": round(ext.area, 0),
                    "close_streets_px": CLOSE_STREETS, "with_streets_area_m2_jgd2000_ix": round(ext_s.area, 0)},
           "on_grid": {"m19_pixels_in_ota": int((m19 & ota).sum()), "rec_pixels_ota": int(rec.sum()),
                       "rec_share_in_m19": round(float(m19[rec].mean()), 4),
                       "m19_share_in_rec": round(float(rec[m19 & ota].mean()), 4) if (m19 & ota).any() else None},
           "on_grid_with_streets": {"m19s_pixels_in_ota": int((m19s & ota).sum()),
                                    "rec_share_in_m19s": round(float(m19s[rec].mean()), 4),
                                    "m19s_share_in_rec": round(float(rec[m19s & ota].mean()), 4) if (m19s & ota).any() else None},
           "sar": {"m19": rates(m19), "m19_not_rec": rates(m19 & ~rec), "ota_rest": rates(~m19),
                   "m19s": rates(m19s), "m19s_not_rec": rates(m19s & ~rec), "ota_rest_s": rates(~m19s)}}
    (OUT / "ota_map.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
