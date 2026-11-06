"""Download the prefectural lists of designated ponds (EXPERIMENT_PLAN.md, データ) into
artifacts/_tameike/tameike-cascade-designation/raw/ and record their SHA-256 in outputs/sources.csv.

  python3 scripts/fetch_lists.py
"""

import csv
import datetime
import hashlib
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
REPO = PROJECT.parents[2]
RAW = REPO / "artifacts/_tameike/tameike-cascade-designation/raw"
KAGAWA = "https://www.pref.kagawa.lg.jp/documents/29845/"
SOURCES = [  # (box, municipality, url)
    ("kagawa", "丸亀市", KAGAWA + "02_boju_marugame08.pdf"),
    ("kagawa", "坂出市", KAGAWA + "03_boju_sakaide08.pdf"),
    ("kagawa", "善通寺市", KAGAWA + "04_boju_zentuji08.pdf"),
    ("kagawa", "三豊市", KAGAWA + "08_boju_mitoyo08.pdf"),
    ("kagawa", "綾川町", KAGAWA + "14_boju_ayagawa08.pdf"),
    ("kagawa", "琴平町", KAGAWA + "15_boju_kotohira08.pdf"),
    ("kagawa", "まんのう町", KAGAWA + "17_boju_mannou08.pdf"),
    ("fukuyama", "", "https://www.pref.hiroshima.lg.jp/uploaded/attachment/674285.pdf"),
    ("awaji", "", "https://web.pref.hyogo.lg.jp/nk11/documents/siteiichiran117.xlsx"),
]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    for box, m, url in SOURCES:
        path = RAW / url.rsplit("/", 1)[1]
        if not path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                path.write_bytes(r.read())
        rows.append(dict(box=box, municipality=m, url=url, file=path.name, bytes=path.stat().st_size,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         fetched=datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()))
    with open(PROJECT / "outputs/sources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r["file"], r["bytes"], r["sha256"][:12])


if __name__ == "__main__":
    main()
