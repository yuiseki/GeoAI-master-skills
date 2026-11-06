"""Match prefectural lists of designated ponds to rows of the MAFF ledger (EXPERIMENT_PLAN.md, 照合のしかた).

  norm   NFKC and no whitespace
  muni   municipality without the county (郡) part
  lot    the first run of digits in an address (the lot number)
  match  for each list row: (ledger source_row, "key1") by municipality + name + lot when that gives one row,
         else (source_row, "key2") by municipality + name when the ledger has that name once there,
         else (source_row, "key3") by municipality + lot + dam height + storage when the list row has both values and
         that gives one ledger row (Hiroshima, whose PDF loses some names),
         else (source_rows, "key4") by municipality + name + the whole address, every ledger row that agrees (Awaji
         lists give only the village, and the ledger repeats some rows),
         else (None, "none"). With loose=True: (all source_rows with the municipality + name, "loose") (B2 b).
"""

import re
import unicodedata
from collections import defaultdict


def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def muni(s):
    return re.sub(r"^.*?郡", "", norm(s))


def lot(s):
    m = re.search(r"\d+", norm(s))
    return m.group(0) if m else ""


def addr(s, m):
    """the whole address without a leading municipality name"""
    s = norm(s)
    return s[len(m):] if m and s.startswith(m) else s


def spec(x):
    """a dam height or storage rounded to 2 decimals, None when missing"""
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def match(lists, ledger, loose=False):
    by_name, by_lot, by_spec, by_addr = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for r in ledger:
        k = (muni(r["municipality"]), norm(r["name"]))
        by_name[k].append(r["source_row"])
        by_lot[k + (lot(r["address"]),)].append(r["source_row"])
        by_addr[k + (addr(r["address"], k[0]),)].append(r["source_row"])
        by_spec[(k[0], lot(r["address"]), spec(r.get("dam_height_m")), spec(r.get("storage_thousand_m3")))].append(
            r["source_row"])
    out = []
    for r in lists:
        k = (muni(r["municipality"]), norm(r["name"]))
        if loose:
            rows = by_name.get(k, [])
            out.append((tuple(rows), "loose") if rows else (None, "none"))
            continue
        a = lot(r["address"])
        hit = by_lot.get(k + (a,), []) if a else []
        if len(hit) == 1:
            out.append((hit[0], "key1"))
        elif len(by_name.get(k, [])) == 1:
            out.append((by_name[k][0], "key2"))
        elif a and spec(r.get("dam_height_m")) is not None and spec(r.get("storage_thousand_m3")) is not None and \
                len(by_spec.get(key3 := (k[0], a, spec(r["dam_height_m"]), spec(r["storage_thousand_m3"])), [])) == 1:
            out.append((by_spec[key3][0], "key3"))
        elif by_addr.get(key4 := k + (addr(r["address"], k[0]),)) and key4[2]:
            out.append((tuple(by_addr[key4]), "key4"))
        else:
            out.append((None, "none"))
    return out
