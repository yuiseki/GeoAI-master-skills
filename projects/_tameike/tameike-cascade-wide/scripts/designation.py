"""B2 of EXPERIMENT_PLAN.md: tameike-cascade-designation's matching on the widened chains.

  systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 -p CPUQuota=200% -- \
    uvx --python 3.12 --with duckdb==1.5.5 --with openpyxl python scripts/designation.py

Lists: every Kagawa municipality's PDF, and the whole Hiroshima and Hyogo lists (raw files in
artifacts/_tameike/tameike-cascade-designation/raw/, fetched here when missing). Ponds in a prefecture without a list
(Tokushima, Okayama) count as unknown. Writes outputs/b2_match.csv, outputs/b2.csv and outputs/candidates.csv.
"""

import csv
import hashlib
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT.parent / "tameike-cascade-designation/scripts"))
from fetch_lists import KAGAWA, RAW, SOURCES  # noqa: E402
from match import match, muni  # noqa: E402
from parse_lists import hiroshima, hyogo, kagawa  # noqa: E402

OUT = PROJECT / "outputs"
TAMEIKE = ("https://huggingface.co/datasets/yuiseki/maff-tameike-list-jp-2026-03/resolve/"
           "ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet")
KAGAWA_ALL = {"高松市": "01_boju_takamatsu08", "丸亀市": "02_boju_marugame08", "坂出市": "03_boju_sakaide08",
              "善通寺市": "04_boju_zentuji08", "観音寺市": "05_boju_kanonji08", "さぬき市": "06_boju_sanuki08",
              "東かがわ市": "07_boju_higasikagawa08", "三豊市": "08_boju_mitoyo08", "土庄町": "09_boju_tonosyou08",
              "小豆島町": "10_boju_syoudosima08", "三木町": "11_boju_miki08", "直島町": "12_boju_naosima08",
              "宇多津町": "13_boju_utadu08", "綾川町": "14_boju_ayagawa08", "琴平町": "15_boju_kotohira08",
              "多度津町": "16_boju_tadotu08", "まんのう町": "17_boju_mannou08"}
LISTED = {"香川県", "広島県", "兵庫県"}


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def get(url):
    path = RAW / url.rsplit("/", 1)[1]
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            path.write_bytes(r.read())
    return path


def lists(sources):
    rows = []
    for m, f in KAGAWA_ALL.items():
        url = KAGAWA + f + ".pdf"
        path = get(url)
        sources.append(dict(file=path.name, url=url, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        rows += [dict(r, pref="香川県") for r in kagawa(path, m)]
    for box, _, url in SOURCES[-2:]:
        path = get(url)
        sources.append(dict(file=path.name, url=url, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        rows += [dict(r, pref="広島県" if box == "fukuyama" else "兵庫県")
                 for r in (hiroshima(path, munis=None) if box == "fukuyama" else hyogo(path, munis=None))]
    return rows


def rows_of(s):
    return {int(x) for x in s.split("|") if x}


def main():
    sources = []
    L_all = lists(sources)
    con = duckdb.connect()
    b2m, b2, cands, led_all = [], [], [], None
    flow_box = {r["box"]: tuple(map(float, r["flow_box"].split())) for r in
                csv.DictReader(open(OUT / "summary.csv", encoding="utf-8"))}
    for key, wb in flow_box.items():
        if led_all is None:
            cur = con.execute(f"""select source_row, name, prefecture, municipality, address, dam_height_m,
                                  storage_thousand_m3 from '{TAMEIKE}'""")
            cols = [d[0] for d in cur.description]
            led_all = [dict(zip(cols, x)) for x in cur.fetchall()]
        inbox = {r[0] for r in con.execute(f"""select source_row from '{TAMEIKE}' where lon between {wb[0]} and {wb[2]}
                                               and lat between {wb[1]} and {wb[3]}""").fetchall()}
        pm = {(r["prefecture"], muni(r["municipality"])) for r in led_all if r["source_row"] in inbox}
        L = [r for r in L_all if (r["pref"], muni(r["municipality"])) in pm]
        led = [r for r in led_all if (r["prefecture"], muni(r["municipality"])) in pm]
        pref_of = {r["source_row"]: r["prefecture"] for r in led}
        spec = {r["source_row"]: r for r in led}
        res = {}
        for mode in ("main", "loose"):
            ms = []
            for pref in LISTED:
                Lp = [r for r in L if r["pref"] == pref]
                ms += list(zip(Lp, match(Lp, [r for r in led if r["prefecture"] == pref], loose=mode == "loose")))
            res[mode] = ms
        how = Counter(h for _, (_, h) in res["main"])
        b2m.append(dict(box=key, municipalities=len(pm), municipalities_listed=sum(p in LISTED for p, _ in pm),
                        listed=len(L), key1=how["key1"], key2=how["key2"], key3=how["key3"], key4=how["key4"],
                        none=how["none"], matched_share=round(1 - how["none"] / len(L), 4)))
        flat = lambda ms: {x for _, (r, _) in ms if r is not None for x in (r if isinstance(r, tuple) else (r,))}
        chains = list(csv.DictReader(open(OUT / f"{key}_chains.csv", encoding="utf-8")))
        c2 = [c for c in chains if int(c["overflowed"]) >= 2 and float(c["people_chain"]) >= 1.0]
        for name, des in (("main", flat(res["main"])), ("loose_all_same_name", flat(res["loose"]))):
            def state(s):
                rs = rows_of(s)
                if rs & des:
                    return "yes"
                return "no" if any(pref_of.get(r) in LISTED for r in rs) else "unknown"
            over = {o for c in c2 for o in c["overflowed_source_rows"].split(" > ")}
            st = Counter(state(c["start_source_rows"]) for c in c2)
            b2.append(dict(box=key, setting=name, chains_2plus_people=len(c2), chain_starts_designated=st["yes"],
                           chain_starts_not_designated=st["no"], chain_starts_unknown=st["unknown"],
                           chain_starts_not_designated_people_ge_100=sum(state(c["start_source_rows"]) == "no" and
                                                                         float(c["people_chain"]) >= 100 for c in c2),
                           overflowed_nodes=len(over),
                           overflowed_nodes_not_designated=sum(state(o) == "no" for o in over),
                           overflowed_nodes_unknown=sum(state(o) == "unknown" for o in over)))
            if name != "main":
                continue
            for c in c2:
                if state(c["start_source_rows"]) != "no":
                    continue
                rs = sorted(rows_of(c["start_source_rows"]))
                cands.append(dict(box=key, start_node=c["start"], start_names=c["start_names"],
                                  source_rows="|".join(map(str, rs)), municipality=spec[rs[0]]["municipality"],
                                  address="|".join(spec[r]["address"] or "" for r in rs),
                                  start_m3=c["start_m3"], start_h_m=c["start_h_m"], overflowed=c["overflowed"],
                                  overflowed_names=c["overflowed_names"],
                                  overflowed_designated=" > ".join(state(o) for o in c["overflowed_source_rows"].split(" > ")),
                                  people_single=c["people_single"], people_chain=c["people_chain"], stop=c["stop"],
                                  end_at_edge=c["end_at_edge"]))
    write(OUT / "b2_match.csv", b2m)
    write(OUT / "b2.csv", b2)
    write(OUT / "candidates.csv", sorted(cands, key=lambda r: (r["box"], -float(r["people_chain"]))))
    write(OUT / "sources.csv", sources)
    for r in b2m + b2:
        print(r)


if __name__ == "__main__":
    main()
