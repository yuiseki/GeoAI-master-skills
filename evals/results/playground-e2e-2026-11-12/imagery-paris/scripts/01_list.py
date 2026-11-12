"""List all Panoramax pictures in Paris 11e (polygon: opendata.paris.fr). Resumable: each tile response is
reduced to feature rows and cached in artifacts/.../tiles/. 4 threads."""
import sys, json, csv, os, hashlib
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/work/.agents/skills/street-imagery-inspection/scripts")
import panoramax_fetch as pf
from shapely.geometry import shape, Point
ART = "/work/artifacts/paris11-street-imagery"
os.makedirs(f"{ART}/tiles", exist_ok=True)
poly = shape(json.load(open("data/arr.json", encoding="utf-8"))["results"][0]["geom"]["geometry"])
bbox = poly.bounds
LIMIT = 1000

def tile(b):
    key = hashlib.md5(repr([round(v, 7) for v in b]).encode()).hexdigest()
    p = f"{ART}/tiles/{key}.json"
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    q = {"bbox": ",".join(f"{v:.7f}" for v in b), "limit": LIMIT}
    import urllib.parse
    got = pf.http_json(f"{pf.API}/search?{urllib.parse.urlencode(q)}").get("features", [])
    rows = [pf.feature_row(f) for f in got]
    json.dump({"n": len(got), "rows": rows}, open(p, "w", encoding="utf-8"))
    print("tile", b, len(got), flush=True)
    return {"n": len(got), "rows": rows}

w, s, e, n = bbox
todo = []
x = w
while x < e:
    y = s
    while y < n:
        todo.append((x, y, min(x + .01, e), min(y + .01, n))); y += .01
    x += .01
seen = {}
with ThreadPoolExecutor(4) as ex:
    while todo:
        res = list(ex.map(tile, todo)); nxt = []
        for b, r in zip(todo, res):
            if r["n"] >= LIMIT and (b[2] - b[0]) > 1e-5:
                mx, my = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                nxt += [(b[0], b[1], mx, my), (mx, b[1], b[2], my), (b[0], my, mx, b[3]), (mx, my, b[2], b[3])]
            else:
                for row in r["rows"]:
                    seen[row["id"]] = row
        todo = nxt
rows = list(seen.values())
inside = [r for r in rows if poly.contains(Point(r["lon"], r["lat"]))]
print(len(rows), "listed in bbox;", len(inside), "inside polygon")
with open(f"{ART}/listed.csv", "w", newline="", encoding="utf-8") as f:
    wr = csv.DictWriter(f, fieldnames=list(inside[0].keys())); wr.writeheader(); wr.writerows(sorted(inside, key=lambda r: r["id"]))
