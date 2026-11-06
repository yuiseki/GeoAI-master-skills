"""Read the raw lists (fetch_lists.py) into artifacts/_tameike/tameike-cascade-designation/designated.csv:
one row per designated pond in the municipalities of the three boxes.

  systemd-run --user --scope -q -p MemoryMax=2G -p MemorySwapMax=0 -- uvx --python 3.12 --with openpyxl \
    python scripts/parse_lists.py

Needs pdftotext (poppler). Kagawa: one PDF per municipality, rows "No. name address". Hiroshima: plan table 2, rows
start with the 9-digit database code; the columns are cut at the word 広島県 because some names do not come out of
the PDF as text. Hyogo: the Excel sheet, a row counts when its 防災重点農業用ため池 date column is not empty.
"""

import csv
import re
import subprocess
from pathlib import Path

import openpyxl

from fetch_lists import RAW, SOURCES

BOX_MUNIS = {"fukuyama": ("福山市", "尾道市", "府中市"), "awaji": ("淡路市", "洲本市")}
OUT = RAW.parent / "designated.csv"


def text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout


def kagawa(path, m):
    rows = []
    for line in text(path).splitlines():
        g = re.match(r"^\s*(\d+)\s+(\S+)\s+(.+?)\s*$", line)
        if g:
            rows.append(dict(box="kagawa", municipality=m, no=int(g.group(1)), name=g.group(2), address=g.group(3),
                             dam_height_m="", storage_thousand_m3=""))
    assert [r["no"] for r in rows] == list(range(1, len(rows) + 1)), path
    return rows


def hiroshima(path, munis=BOX_MUNIS["fukuyama"]):
    rows = []
    for line in text(path).splitlines():
        g = re.match(r"^\s*(34\d{7})\s+(.*?)\s*広島県\s+(\S+)\s+(.+)$", line)
        if not g or (munis is not None and g.group(3) not in munis):
            continue
        code, before, m, rest = g.groups()
        parts = re.split(r"\s{2,}", before.strip()) if before.strip() else []
        name = parts[0] if len(parts) == 2 else ""          # name and furigana; one part means the name is missing
        nums = re.findall(r"\s(\d+\.\d+)", rest)
        addr = re.split(r"\s{2,}", rest.strip())[0]
        rows.append(dict(box="fukuyama", municipality=m, no=code, name=name, address=addr,
                         dam_height_m=nums[0] if len(nums) >= 3 else "",
                         storage_thousand_m3=nums[2] if len(nums) >= 3 else ""))
    return rows


def hyogo(path, munis=BOX_MUNIS["awaji"]):
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = []
    for r in ws.iter_rows(min_row=6, values_only=True):
        code, _, name, m, addr, _, _, bousai = r[:8]
        if m and (munis is None or any(m.startswith(x) for x in munis)) and bousai:
            rows.append(dict(box="awaji", municipality=m, no=code, name=name or "", address=addr or "",
                             dam_height_m="", storage_thousand_m3=""))
    return rows


def main():
    rows = []
    for box, m, url in SOURCES:
        path = RAW / url.rsplit("/", 1)[1]
        rows += kagawa(path, m) if box == "kagawa" else hiroshima(path) if box == "fukuyama" else hyogo(path)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(Counter((r["box"], r["municipality"]) for r in rows))
    print("no name", Counter(r["box"] for r in rows if not r["name"]))


if __name__ == "__main__":
    main()
