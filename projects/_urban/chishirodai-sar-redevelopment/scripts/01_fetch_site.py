"""Save the outline of the site: the OSM way tagged landuse=construction, construction=commercial at 千城台東 2 丁目.

python3 scripts/01_fetch_site.py

Reads way 1423054131 from the requester's own Overpass (overpass.yuiseki.net, data frozen at 2025-09-14; the public OSM
servers are not used) and writes labels/site.geojson with the way's tags, version and edit time. The outline is the
area mapped as under construction in 2025-08; drawn over the GSI photos (07_site_photos.py) it covers nearly the whole
fan-shaped block whose buildings disappeared.
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WAY = 1423054131
URL = "https://overpass.yuiseki.net/api/interpreter"


def main():
    q = f"[out:json][timeout:60];way({WAY});out meta geom;"
    req = urllib.request.Request(URL, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "GeoAI-master-skills/chishirodai-sar-redevelopment"})
    r = json.loads(urllib.request.urlopen(req, timeout=90).read())  # the default urllib agent gets 403
    (e,) = r["elements"]
    ring = [[p["lon"], p["lat"]] for p in e["geometry"]]
    if ring[0] != ring[-1]:
        raise RuntimeError("way is not closed")
    fc = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"osm_way": WAY, "version": e["version"], "timestamp": e["timestamp"], **e["tags"],
                       "source": f"{URL} (osm_base {r['osm3s'].get('timestamp_osm_base')})",
                       "licence": "© OpenStreetMap contributors, ODbL 1.0"}}]}
    (HERE.parent / "labels/site.geojson").write_text(json.dumps(fc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(e["tags"], e["version"], e["timestamp"], len(ring))


if __name__ == "__main__":
    main()
