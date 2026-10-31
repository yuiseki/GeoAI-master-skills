"""Fetch the inputs of stage B into artifacts/_flood/kita-inbanuma-sar-replication/raw_b/.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with pyproj --with pymupdf python scripts/07_fetch_b.py

- GSI depth tiles (dansaizu) of the four versions at z16 over the box around the stage A comparison window.
- The four PDF maps (pinned revision of the HF dataset) and the legend image with its mask taken out of each.
- Sentinel-1 GRD of 2026-09-12, 09-24 and 10-06 (orbit 39), and 09-19 and 10-01 (orbit 141): VV and VH windows in
  radar geometry covering the
  analysis box, with the product, calibration and noise annotations of each polarisation.
- Sentinel-1 RTC of 2026-09-19 and 10-01 (orbit 141), cut like stage A.
Every file is listed in raw_b/MANIFEST.json (URL without the SAS token, bytes, sha256). Existing files are kept.
"""
import json
import math
import re
import sys
import time
import urllib.error
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
fa = __import__("01_fetch")
ART = fa.RAW.parent
RAW_B = ART / "raw_b"
HF = "https://huggingface.co/datasets/yuiseki/gsi-inundation-estimate-kita-inbanuma-jp-2026-10/resolve/e760fbab7cdad6bc7de9adf78320cf3eca7ff288/"
VERSIONS = ["0922", "0924", "0925", "1001"]
GRD = {"0912": "S1C_IW_GRDH_1SDV_20260912T084126_20260912T084151_009412_012B80",
       "0924": "S1C_IW_GRDH_1SDV_20260924T084127_20260924T084152_009587_01313D",
       "1006": "S1C_IW_GRDH_1SDV_20261006T084127_20261006T084152_009762_013716",
       "0919": "S1C_IW_GRDH_1SDV_20260919T083258_20260919T083327_009514_012EDD",
       "1001": "S1C_IW_GRDH_1SDV_20261001T083258_20261001T083328_009689_0134B3"}
ORBIT = {"0912": 39, "0924": 39, "1006": 39, "0919": 141, "1001": 141}
RTC_141 = {"0919": "S1C_IW_GRDH_1SDV_20260919T083258_20260919T083327_009514_012EDD_rtc",
           "1001": "S1C_IW_GRDH_1SDV_20261001T083258_20261001T083328_009689_0134B3_rtc"}
Z = 16


def window_lonlat():
    """Lon/lat box of the stage A comparison window, widened by 500 m."""
    win = np.load(ART / "windows.npz")["buffer"]
    g = np.load(ART / "grid.npz")
    a, _, c, _, e, f = g["transform"]
    rows, cols = np.where(win)
    x0, x1 = c + cols.min() * a - 500, c + (cols.max() + 1) * a + 500
    y0, y1 = f + (rows.max() + 1) * e - 500, f + rows.min() * e + 500
    return fa.lonlat_box((x0, y0, x1, y1))


def geolocation_points(xml):
    pts = re.findall(r"<geolocationGridPoint>(.*?)</geolocationGridPoint>", xml, re.S)
    out = {k: [] for k in ("line", "pixel", "latitude", "longitude", "height", "incidenceAngle")}
    for p in pts:
        for k in out:
            out[k].append(float(re.search(rf"<{k}>([^<]+)</{k}>", p).group(1)))
    return {k: np.array(v) for k, v in out.items()}


def radar_window(geo_pts, lb, margin=150):
    """Rows and columns of the GRD covering the lon/lat box, from the geolocation grid (linear in lon, lat)."""
    a = np.column_stack([np.ones_like(geo_pts["longitude"]), geo_pts["longitude"], geo_pts["latitude"]])
    cl = np.linalg.lstsq(a, geo_pts["line"], rcond=None)[0]
    cp = np.linalg.lstsq(a, geo_pts["pixel"], rcond=None)[0]
    corners = np.array([[1, lb[0], lb[1]], [1, lb[2], lb[1]], [1, lb[0], lb[3]], [1, lb[2], lb[3]]])
    lines, pixels = corners @ cl, corners @ cp
    r0, r1 = int(lines.min()) - margin, int(lines.max()) + margin
    c0, c1 = int(pixels.min()) - margin, int(pixels.max()) + margin
    return max(r0, 0), max(c0, 0), r1, c1


def main():
    RAW_B.mkdir(parents=True, exist_ok=True)
    manifest = []
    lb = window_lonlat()
    box_a = fa.fetch_box()
    print("tile box", [round(v, 4) for v in lb])

    xs = [int((lb[0] + 180) / 360 * 2 ** Z), int((lb[2] + 180) / 360 * 2 ** Z)]
    ys = [int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2 ** Z) for lat in (lb[3], lb[1])]
    for v in VERSIONS:
        layer = f"20260924typhoon25_kitainbanuma_{v}dansaizu"
        d = RAW_B / "tiles" / v
        d.mkdir(parents=True, exist_ok=True)
        n404 = 0
        for x in range(xs[0], xs[1] + 1):
            for y in range(ys[0], ys[1] + 1):
                p, miss = d / f"{x}_{y}.png", d / f"{x}_{y}.404"
                url = f"https://cyberjapandata.gsi.go.jp/xyz/{layer}/{Z}/{x}/{y}.png"
                if not p.exists() and not miss.exists():
                    try:
                        p.write_bytes(fa.get(url))
                    except urllib.error.HTTPError:
                        miss.write_text("404\n", encoding="utf-8")
                    time.sleep(0.05)
                if miss.exists():
                    n404 += 1
                else:
                    manifest.append({"path": str(p.relative_to(RAW_B)), "url": url})
        print(v, "tiles", (xs[1] - xs[0] + 1) * (ys[1] - ys[0] + 1), "404", n404)

    import fitz  # pymupdf
    for v in VERSIONS:
        day = f"2026{v}"
        p = RAW_B / "pdf" / f"shinsui_kita-inbanuma_{day}.pdf"
        p.parent.mkdir(parents=True, exist_ok=True)
        url = f"{HF}raw/2026-10-31/{day}/shinsui_kita-inbanuma_{day}.pdf"
        if not p.exists():
            p.write_bytes(fa.get(url))
        manifest.append({"path": str(p.relative_to(RAW_B)), "url": url})
        doc = fitz.open(p)
        with_mask = [im for im in doc[0].get_images(full=True) if im[1] != 0]
        if len(with_mask) != 1:
            raise RuntimeError(f"{p.name}: expected one image with a mask (the legend), got {len(with_mask)}")
        xref, smask = with_mask[0][0], with_mask[0][1]
        rgb, alpha = fitz.Pixmap(doc, xref), fitz.Pixmap(doc, smask)
        np.savez_compressed(RAW_B / "pdf" / f"legend_{v}.npz",
                            rgb=np.frombuffer(rgb.samples, np.uint8).reshape(rgb.h, rgb.w, rgb.n)[..., :3],
                            alpha=np.frombuffer(alpha.samples, np.uint8).reshape(alpha.h, alpha.w))

    tok = None
    for tag, item_id in GRD.items():
        d = RAW_B / "grd" / tag
        d.mkdir(parents=True, exist_ok=True)
        ip = d / "item.json"
        if not ip.exists():
            ip.write_bytes(fa.get(f"{fa.STAC}/collections/sentinel-1-grd/items/{item_id}"))
        item = json.loads(ip.read_text(encoding="utf-8"))
        assert item["properties"]["sat:relative_orbit"] == ORBIT[tag]
        manifest.append({"path": str(ip.relative_to(RAW_B)), "url": f"{fa.STAC}/collections/sentinel-1-grd/items/{item_id}"})
        for pol in ("vv", "vh"):
            href = item["assets"][pol]["href"]
            base = href.rsplit("/measurement/", 1)[0]
            files = {"product": f"{base}/annotation/iw-{pol}.xml", "calibration": item["assets"][f"schema-calibration-{pol}"]["href"],
                     "noise": item["assets"][f"schema-noise-{pol}"]["href"]}
            for k, u in files.items():
                fp = d / f"{k}-{pol}.xml"
                if not fp.exists():
                    tok = tok or fa.token(href)
                    fp.write_bytes(fa.get(f"{u}?{tok}"))
                manifest.append({"path": str(fp.relative_to(RAW_B)), "url": u})
            mp = d / f"{pol}.tif"
            if not mp.exists():
                tok = tok or fa.token(href)
                pts = geolocation_points((d / f"product-{pol}.xml").read_text(encoding="utf-8"))
                r0, c0, r1, c1 = radar_window(pts, fa.lonlat_box(box_a))
                with rasterio.open(f"{href}?{tok}") as src:
                    r1, c1 = min(r1, src.height), min(c1, src.width)
                    data = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))
                prof = {"driver": "GTiff", "dtype": data.dtype, "count": 1, "width": data.shape[1], "height": data.shape[0],
                        "compress": "deflate"}
                with rasterio.open(mp, "w", **prof) as dst:
                    dst.write(data, 1)
                    dst.update_tags(row_off=r0, col_off=c0)
            manifest.append({"path": str(mp.relative_to(RAW_B)), "url": href})

    rtc_tok = None
    for tag, item_id in RTC_141.items():
        ip = RAW_B / f"rtc141_{tag}_item.json"
        if not ip.exists():
            ip.write_bytes(fa.get(f"{fa.STAC}/collections/sentinel-1-rtc/items/{item_id}"))
        item = json.loads(ip.read_text(encoding="utf-8"))
        assert item["properties"]["sat:relative_orbit"] == 141 and item["properties"]["proj:epsg"] == 32654
        manifest.append({"path": ip.name, "url": f"{fa.STAC}/collections/sentinel-1-rtc/items/{item_id}"})
        for pol in ("vv", "vh"):
            p = RAW_B / f"rtc141_{tag}_{pol}.tif"
            href = item["assets"][pol]["href"]
            if not p.exists():
                rtc_tok = rtc_tok or fa.token(href)
                fa.cut(href, rtc_tok, box_a, p)
            manifest.append({"path": p.name, "url": href})

    for m in manifest:
        p = RAW_B / m["path"]
        m.update(bytes=p.stat().st_size, sha256=fa.sha(p))
    (RAW_B / "MANIFEST.json").write_text(json.dumps({"tile_box_lonlat": lb, "files": manifest}, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8")
    print("files", len(manifest))


if __name__ == "__main__":
    main()
