"""Download the KSJ zips listed in a CSV (from the mlit-nlftp catalog) one at a time, with a pause, skipping files
already there. A browser-like User-Agent is sent: the default one of urllib gets 403 from the server's CDN.

Usage:
    python3 fetch_ksj.py FILES.csv OUT_DIR [--pause 1.0]
"""

import argparse
import csv
import os
import time
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files")
    ap.add_argument("out")
    ap.add_argument("--pause", type=float, default=1.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = list(csv.DictReader(open(a.files)))
    got = 0
    for k, r in enumerate(rows):
        path = os.path.join(a.out, r["href"].rsplit("/", 1)[1])
        if os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        req = urllib.request.Request(r["href"], headers={"User-Agent": "Mozilla/5.0 (research script)"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(path + ".part", "wb") as fh:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
        os.replace(path + ".part", path)
        got += 1
        print(f"{k + 1}/{len(rows)} {r['collection']} {os.path.basename(path)} {os.path.getsize(path) / 1e6:.1f} MB", flush=True)
        time.sleep(a.pause)
    print(f"downloaded {got}, total files {len(rows)}")


if __name__ == "__main__":
    main()
