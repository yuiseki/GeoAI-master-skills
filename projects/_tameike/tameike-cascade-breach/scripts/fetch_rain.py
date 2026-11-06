"""Daily maximum 1-hour precipitation, 1976-2025, for the JMA stations used in this project, from the JMA
"過去の気象データ・ダウンロード" form (see dataset-discovery/references/jma-obsdl.md). One request per station.
Saves the CSV as returned (cp932) under artifacts/_tameike/tameike-cascade-breach/rain/ with its sha256, and writes
outputs/rain_annual_max.csv (station, year, annual maximum of the daily 1-hour maximum, days with quality 8 or 5).

  python3 scripts/fetch_rain.py
"""

import csv
import hashlib
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
REPO = PROJECT.parents[2]
ART = REPO / "artifacts/_tameike/tameike-cascade-breach/rain"
OUT = PROJECT / "outputs"
STATIONS = {  # station id: (name, box it serves, role)
    "a0729": ("滝宮", "kagawa", "main"), "s47891": ("高松", "kagawa", "alt"),
    "s47767": ("福山", "fukuyama", "main"), "a0951": ("府中", "fukuyama", "alt"),
    "a0970": ("郡家", "awaji", "main"), "s47776": ("洲本", "awaji", "alt"),
}
Y0, Y1 = 1976, 2025


def fetch(stid):
    path = ART / f"{stid}_{Y0}_{Y1}.csv"
    if not path.exists():
        form = dict(stationNumList=json.dumps([stid]), aggrgPeriod="1", elementNumList=json.dumps([["105", "1"]]),
                    interAnnualFlag="1", ymdList=json.dumps([str(Y0), str(Y1), "1", "12", "1", "31"]),
                    optionNumList="[]", downloadFlag="true", rmkFlag="1", disconnectFlag="1", youbiFlag="0",
                    fukenFlag="0", kijiFlag="0", huukouFlag="0", csvFlag="1", jikantaiFlag="0", jikantaiList="[]",
                    ymdLiteral="1", interAnnualType="1", option=json.dumps({"list": ["obs"], "nyear": 0}))
        req = urllib.request.Request("https://www.data.jma.go.jp/risk/obsdl/show/table",
                                     data=urllib.parse.urlencode(form).encode(),
                                     headers={"Origin": "https://www.data.jma.go.jp",
                                              "Referer": "https://www.data.jma.go.jp/risk/obsdl/index.php"})
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read()
        if b"<html" in body[:200].lower():
            raise SystemExit(f"{stid}: the form returned a page, not a CSV")
        ART.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return path


def annual_max(path):
    lines = path.read_bytes().decode("cp932").splitlines()
    rows = list(csv.reader(io.StringIO("\n".join(lines[6:]))))
    years = {}
    for r in rows:
        if not r or not r[0][:4].isdigit():
            continue
        y = int(r[0][:4])
        val, quality = r[1], r[-2]
        d = years.setdefault(y, dict(max_mm=None, days_ok=0))
        if quality in ("8", "5") and val != "":
            d["days_ok"] += 1
            v = float(val)
            if d["max_mm"] is None or v > d["max_mm"]:
                d["max_mm"] = v
    return years


def main():
    out = []
    for stid, (name, box, role) in STATIONS.items():
        path = fetch(stid)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        for y, d in sorted(annual_max(path).items()):
            out.append(dict(station=stid, name=name, box=box, role=role, year=y, max_1h_mm=d["max_mm"],
                            days_ok=d["days_ok"], csv_sha256_16=sha))
        print(stid, name, sum(1 for o in out if o["station"] == stid), "years", flush=True)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "rain_annual_max.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
