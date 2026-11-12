"""OSM power=pole and highway=street_lamp, support=pole in Paris 11e via Overpass (date recorded)."""
import json, urllib.request, urllib.parse, datetime
from shapely.geometry import shape, Point
poly = shape(json.load(open("data/arr.json", encoding="utf-8"))["results"][0]["geom"]["geometry"])
w,s,e,n = poly.bounds
q = f'[out:json][timeout:120];(node["power"="pole"]({s},{w},{n},{e});node["highway"="street_lamp"]({s},{w},{n},{e}););out;'
req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent":"geoai-study"})
d = json.load(urllib.request.urlopen(req, timeout=180))
els = [x for x in d["elements"] if poly.contains(Point(x["lon"], x["lat"]))]
json.dump({"fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(), "osm_base": d.get("osm3s",{}), "elements": els}, open("/work/artifacts/paris11-street-imagery/osm_poles.json","w"))
from collections import Counter
print(len(els), Counter(("lamp" if x["tags"].get("highway")=="street_lamp" else "pole") for x in els))
