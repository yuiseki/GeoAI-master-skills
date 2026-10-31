"""Our own GRD processing (EXPERIMENT_PLAN_B.md, GRD の処理), and its check against the RTC scene of 2026-09-24.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with scipy --with pyproj python scripts/09_grd.py

For each GRD (0912, 0924, 1006) and polarisation: sigma0 from the calibration and noise annotations, put on the
analysis grid with the geolocation grid and the DEM moved to ellipsoidal heights (DEM5A/DEM10B + the EGM96 geoid
height from PROJ), and divided by cos(incidence) to give gamma0 on the ellipsoid. Writes artifacts/.../grd_<tag>.npz
(vv, vh in dB) and outputs/grd_check.json. Stops with exit 1 when the check fails for any scene: a shift of 1 pixel or
more in rows or columns between its VV and the WorldCover 2021 permanent water (the check of the plan as changed on
2026-10-31; the shifts of the RTC scenes and of the GRD against the RTC scene of 09-24 are written alongside).
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pyproj
import rasterio
from pyproj import Transformer
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
fb = __import__("07_fetch_b")
from sar import to_db  # noqa: E402
from sarb import Geolocation, azimuth_noise, sample_bilinear, shift_by_correlation, sigma0, vectors_to_grid  # noqa: E402

OUT = HERE.parent / "outputs"
UTM = "EPSG:32654"


def floats(s):
    return np.array([float(v) for v in s.split()])


def calibration_vectors(xml):
    vs = re.findall(r"<calibrationVector>(.*?)</calibrationVector>", xml, re.S)
    lines = [int(re.search(r"<line>(\d+)</line>", v).group(1)) for v in vs]
    pixels = [floats(re.search(r"<pixel[^>]*>([^<]+)</pixel>", v).group(1)) for v in vs]
    sig = [floats(re.search(r"<sigmaNought[^>]*>([^<]+)</sigmaNought>", v).group(1)) for v in vs]
    return lines, pixels, sig


def noise_vectors(xml):
    rv = re.findall(r"<noiseRangeVector>(.*?)</noiseRangeVector>", xml, re.S)
    lines = [int(re.search(r"<line>(\d+)</line>", v).group(1)) for v in rv]
    pixels = [floats(re.search(r"<pixel[^>]*>([^<]+)</pixel>", v).group(1)) for v in rv]
    lut = [floats(re.search(r"<noiseRangeLut[^>]*>([^<]+)</noiseRangeLut>", v).group(1)) for v in rv]
    blocks = []
    for v in re.findall(r"<noiseAzimuthVector>(.*?)</noiseAzimuthVector>", xml, re.S):
        get = lambda k: int(re.search(rf"<{k}>(\d+)</{k}>", v).group(1))  # noqa: E731
        blocks.append((get("firstAzimuthLine"), get("lastAzimuthLine"), get("firstRangeSample"), get("lastRangeSample"),
                       floats(re.search(r"<line[^>]*>([^<]+)</line>", v).group(1)),
                       floats(re.search(r"<noiseAzimuthLut[^>]*>([^<]+)</noiseAzimuthLut>", v).group(1))))
    return lines, pixels, lut, blocks


def radar_sigma0(d, pol):
    with rasterio.open(d / f"{pol}.tif") as src:
        dn = src.read(1)
        tags = src.tags()
    r0, c0 = int(tags["row_off"]), int(tags["col_off"])
    rows, cols = r0 + np.arange(dn.shape[0]), c0 + np.arange(dn.shape[1])
    cl, cp, cs = calibration_vectors((d / f"calibration-{pol}.xml").read_text(encoding="utf-8"))
    nl, npx, nlut, blocks = noise_vectors((d / f"noise-{pol}.xml").read_text(encoding="utf-8"))
    a = vectors_to_grid(cl, cp, cs, rows, cols)
    noise = vectors_to_grid(nl, npx, nlut, rows, cols) * azimuth_noise(blocks, rows, cols)
    return sigma0(dn, a, noise), r0, c0, {"dn_zero": int((dn == 0).sum()), "shape": list(dn.shape)}


def ellipsoidal_dem(g, lon, lat):
    """DEM (orthometric) + EGM96 geoid height, the geoid computed every 50 pixels and interpolated."""
    pyproj.network.set_network_enabled(True)
    t = Transformer.from_crs("EPSG:4326+5773", "EPSG:4979", always_xy=True)
    sub = (slice(None, None, 50), slice(None, None, 50))
    _, _, h = t.transform(lon[sub], lat[sub], np.zeros(lon[sub].shape))
    h = np.asarray(h)
    if not np.isfinite(h).all() or np.abs(h).max() > 200:
        raise RuntimeError("geoid heights were not computed (is the PROJ network reachable?)")
    rr = np.arange(lon.shape[0]) / 50
    cc = np.arange(lon.shape[1]) / 50
    geoid = ndimage.map_coordinates(h, np.meshgrid(rr, cc, indexing="ij"), order=1, mode="nearest")
    return g["dem"] + geoid, geoid


def main():
    g = np.load(fb.ART / "grid.npz")
    shape = g["vv_a"].shape
    a, _, c, _, e, f = g["transform"]
    rows, cols = np.mgrid[0:shape[0], 0:shape[1]]
    x, y = c + (cols + 0.5) * a, f + (rows + 0.5) * e
    lon, lat = (np.asarray(v) for v in Transformer.from_crs(UTM, "EPSG:4326", always_xy=True).transform(x, y))
    h_ell, geoid = ellipsoidal_dem(g, lon, lat)
    info = {"geoid_m": [round(float(geoid.min()), 3), round(float(geoid.max()), 3)], "scenes": {}}
    for tag in fb.GRD:
        d = fb.RAW_B / "grd" / tag
        out = {}
        for pol in ("vv", "vh"):
            pts = fb.geolocation_points((d / f"product-{pol}.xml").read_text(encoding="utf-8"))
            spacing = float(re.search(r"<rangePixelSpacing>([^<]+)<", (d / f"product-{pol}.xml").read_text(encoding="utf-8")).group(1))
            geo = Geolocation(pts["line"], pts["pixel"], pts["longitude"], pts["latitude"], pts["height"], pts["incidenceAngle"], spacing)
            s0, r0, c0, meta = radar_sigma0(d, pol)
            line, pix, inc = geo(lon, lat, h_ell)
            lin = sample_bilinear(s0, line - r0, pix - c0) / np.cos(np.radians(inc))
            out[pol] = to_db(lin).astype(np.float32)
            info["scenes"].setdefault(tag, {})[pol] = {**meta,
                                                       "missing_on_grid": int(np.isnan(out[pol]).sum()),
                                                       "incidence_deg": [round(float(inc.min()), 2), round(float(inc.max()), 2)]}
        np.savez_compressed(fb.ART / f"grd_{tag}.npz", **out)

    win = np.load(fb.ART / "windows.npz")["buffer"]
    rws, cls = np.where(win)
    box = (slice(rws.min() - 200, rws.max() + 200), slice(cls.min() - 200, cls.max() + 200))
    ref = -g["water"][box].astype(float)  # permanent water is dark in VV
    checks = {}
    for tag in fb.GRD:
        vv = np.load(fb.ART / f"grd_{tag}.npz")["vv"]
        dr, dc, score = shift_by_correlation(ref, np.clip(vv[box], -25, 0), max_shift=8)
        checks[tag] = {"shift_rows_px": round(dr, 3), "shift_cols_px": round(dc, 3), "correlation": round(score, 4),
                       "pass": bool(abs(dr) < 1 and abs(dc) < 1)}
    for name, img in (("rtc_0912", g["vv_b"]), ("rtc_0924", g["vv_a"])):
        dr, dc, score = shift_by_correlation(ref, np.clip(img[box], -25, 0), max_shift=8)
        checks[name] = {"shift_rows_px": round(dr, 3), "shift_cols_px": round(dc, 3), "correlation": round(score, 4)}
    grd = np.load(fb.ART / "grd_0924.npz")
    b2 = (slice(rws.min(), rws.max() + 1), slice(cls.min(), cls.max() + 1))
    dr, dc, score = shift_by_correlation(g["vv_a"][b2], grd["vv"][b2])
    m = win[b2]
    checks["grd_vs_rtc_0924"] = {"shift_rows_px": round(dr, 3), "shift_cols_px": round(dc, 3), "correlation": round(score, 4),
                                 "median_db_grd_minus_rtc": {pol: round(float(np.median((grd[pol][b2] - g[f"{pol}_a"][b2])[m])), 3)
                                                             for pol in ("vv", "vh")}}
    info["check_against_worldcover"] = checks
    (OUT / "grd_check.json").write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False))
    if not all(checks[t]["pass"] for t in fb.GRD):
        sys.exit(1)


if __name__ == "__main__":
    main()
