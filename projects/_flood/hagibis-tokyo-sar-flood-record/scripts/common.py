"""Shared constants and helpers: the analysis box, the dates of EXPERIMENT_PLAN.md, the inputs, and HTTP fetching."""
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
ART = ROOT / "artifacts/_flood/hagibis-tokyo-sar-flood-record"
RAW = ART / "raw"
OUT = HERE.parent / "outputs"
UTM = "EPSG:32654"
BOX_LONLAT = (139.18, 35.55, 139.70, 35.75)  # west, south, east, north
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
OVERPASS = "https://overpass.yuiseki.net/api/interpreter"  # the requester's own; the public OSM servers are not used

# local working trees of the published datasets (HF yuiseki/<name>), read only
FLOOD_RECORD = Path("/sata_hdd_24tb/hf_data/tokyo-flood-record-jp/data/parquet/flood_area.parquet")
A31A_MAX = Path("/sata_hdd_24tb/hf_data/ksj-a31a-flood-greater-tokyo/data/parquet/categories/maximum.parquet")
N03_TOKYO = Path("/sata_hdd_24tb/hf_data/ksj-a31a-flood-greater-tokyo/data/docs/N03-20260101_13_GML.zip")

# the scenes of the plan, by orbit: (role, UTC date of the acquisition). Items of one date are merged.
SCENES = {
    46: [("pre", "2019-07-26"), ("pre", "2019-08-07"), ("pre", "2019-08-19"), ("pre", "2019-09-12"),
         ("pre", "2019-09-24"), ("pre", "2019-10-06"), ("event", "2019-10-12"), ("after", "2019-10-18"),
         ("after", "2019-10-30")],
    39: [("pre", "2019-07-20"), ("pre", "2019-08-01"), ("pre", "2019-08-13"), ("pre", "2019-08-25"),
         ("pre", "2019-09-06"), ("pre", "2019-09-18"), ("pre", "2019-09-30"), ("event", "2019-10-12"),
         ("after", "2019-10-18"), ("after", "2019-10-24")],
}


def box_utm():
    """The UTM box covering BOX_LONLAT, snapped outward to 10 m (the RTC grids have origins on multiples of 10 m)."""
    w, s, e, n = BOX_LONLAT
    t = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    xs, ys = t.transform([w, e, w, e], [s, s, n, n])
    return (math.floor(min(xs) / 10) * 10, math.floor(min(ys) / 10) * 10,
            math.ceil(max(xs) / 10) * 10, math.ceil(max(ys) / 10) * 10)


def get(url, data=None, tries=5, headers=None):
    for i in range(tries):
        try:
            h = dict(headers or {})
            if data and "content-type" not in {k.lower() for k in h}:
                h["content-type"] = "application/json"
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=180) as r:
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
