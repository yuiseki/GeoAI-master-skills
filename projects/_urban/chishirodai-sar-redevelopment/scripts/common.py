"""Shared constants and helpers: the analysis box (12 x 12 web-mercator z16 tiles around the site) and HTTP fetching."""
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

from pyproj import Transformer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ART = ROOT / "artifacts/_urban/chishirodai-sar-redevelopment"
RAW = ART / "raw"
OUT = HERE.parent / "outputs"
UTM = "EPSG:32654"
SITE = (140.1949078559463, 35.61884481509456)  # 千葉市若葉区千城台東 2-13 (the point given by the requester)
Z = 16
TX = range(58284, 58296)  # 12 tiles; the site is in tile (58289, 25820)
TY = range(25815, 25827)
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token"


def tile_lonlat_bounds(x, y, z=Z):
    """(west, south, east, north) in degrees of the web-mercator tile."""
    n = 2 ** z

    def lat(yy):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
    return x / n * 360 - 180, lat(y + 1), (x + 1) / n * 360 - 180, lat(y)


def box_lonlat():
    w, _, _, n = tile_lonlat_bounds(TX[0], TY[0])
    _, s, e, _ = tile_lonlat_bounds(TX[-1], TY[-1])
    return w, s, e, n


def box_utm(margin=200):
    """The UTM box covering all tiles plus a margin, snapped outward to 10 m."""
    w, s, e, n = box_lonlat()
    t = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    xs, ys = t.transform([w, e, w, e], [s, s, n, n])
    x0, y0 = math.floor((min(xs) - margin) / 10) * 10, math.floor((min(ys) - margin) / 10) * 10
    x1, y1 = math.ceil((max(xs) + margin) / 10) * 10, math.ceil((max(ys) + margin) / 10) * 10
    return x0, y0, x1, y1


def get(url, data=None, tries=5, headers=None):
    for i in range(tries):
        try:
            h = dict(headers or {})
            if data:
                h["content-type"] = "application/json"
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            time.sleep(3 * (i + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"failed: {url}")


def stac_search(body):
    """All features of a STAC search, following the next links."""
    feats, url, data = [], f"{STAC}/search", json.dumps(body).encode()
    while True:
        r = json.loads(get(url, data=data))
        feats += r["features"]
        nxt = [lk for lk in r.get("links", []) if lk["rel"] == "next"]
        if not nxt:
            return feats
        url = nxt[0]["href"]
        data = json.dumps(nxt[0]["body"]).encode() if nxt[0].get("body") else None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def token(href):
    account = href.split("//")[1].split(".")[0]
    container = href.split("/")[3]
    return json.loads(get(f"{SAS}/{account}/{container}"))["token"]
