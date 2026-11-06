"""B0-B2 of EXPERIMENT_PLAN.md.

  systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 -p CPUQuota=200% -- \
    uvx --python 3.12 --with duckdb==1.5.5 python scripts/run_match.py

Reads artifacts/.../designated.csv (parse_lists.py), the ledger, and tameike-cascade-breach/outputs/<box>_chains.csv
(main setting, with the ledger rows of each node). Writes outputs/b0_match.csv, outputs/b1.csv (B1 and B2) and
outputs/candidates.csv (chain starts that are not designated). Rows of the lists that match nothing go to
artifacts/.../unmatched.csv.
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

from fetch_lists import RAW
from match import match, muni

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "outputs"
BREACH = PROJECT.parent / "tameike-cascade-breach/outputs"
TAMEIKE = ("https://huggingface.co/datasets/yuiseki/maff-tameike-list-jp-2026-03/resolve/"
           "ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet")
PREF = {"kagawa": "香川県", "fukuyama": "広島県", "awaji": "兵庫県"}


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def ledger(box, munis):
    con = duckdb.connect()
    cur = con.execute(f"""select source_row, name, municipality, address, dam_height_m, storage_thousand_m3
                          from '{TAMEIKE}' where prefecture = '{PREF[box]}'""")
    cols = [d[0] for d in cur.description]
    return [r for r in (dict(zip(cols, x)) for x in cur.fetchall()) if muni(r["municipality"]) in munis]


def rows_of(s):
    return {int(x) for x in s.split("|") if x}


def main():
    lists = list(csv.DictReader(open(RAW.parent / "designated.csv", encoding="utf-8")))
    b0, b1, cands, unmatched = [], [], [], []
    for box in PREF:
        L = [r for r in lists if r["box"] == box]
        munis = {muni(r["municipality"]) for r in L}
        led = ledger(box, munis)
        main_m = match(L, led)  # a match is one source_row, or a tuple of them (key 4)
        key1 = [(r, h) if h == "key1" else (None, "none") for r, h in main_m]
        loose = match(L, led, loose=True)
        spec = {r["source_row"]: r for r in led}
        for m in sorted(munis):
            idx = [i for i, r in enumerate(L) if muni(r["municipality"]) == m]
            how = Counter(main_m[i][1] for i in idx)
            # Hiroshima lists height and storage: do matched pairs agree with the ledger?
            agree = [abs(float(L[i]["dam_height_m"]) - (spec[main_m[i][0]]["dam_height_m"] or 0)) < 0.05
                     and abs(float(L[i]["storage_thousand_m3"]) - (spec[main_m[i][0]]["storage_thousand_m3"] or 0)) < 0.005
                     for i in idx if isinstance(main_m[i][0], int) and L[i]["dam_height_m"] and L[i]["storage_thousand_m3"]]
            b0.append(dict(box=box, municipality=m, listed=len(idx), ledger_rows=sum(muni(r["municipality"]) == m for r in led),
                           key1=how["key1"], key2=how["key2"], key3=how["key3"], key4=how["key4"], none=how["none"],
                           matched_share=round(1 - how["none"] / len(idx), 4),
                           spec_checked=len(agree), spec_agree=sum(agree)))
            unmatched += [L[i] for i in idx if main_m[i][0] is None]
        tot = [r for r in b0 if r["box"] == box]
        n, nn = sum(r["listed"] for r in tot), sum(r["none"] for r in tot)
        b0.append(dict(box=box, municipality="(all)", listed=n, ledger_rows=sum(r["ledger_rows"] for r in tot),
                       key1=sum(r["key1"] for r in tot), key2=sum(r["key2"] for r in tot), key3=sum(r["key3"] for r in tot),
                       key4=sum(r["key4"] for r in tot),
                       none=nn, matched_share=round(1 - nn / n, 4), spec_checked=sum(r["spec_checked"] for r in tot),
                       spec_agree=sum(r["spec_agree"] for r in tot)))

        flat = lambda ms: {x for r, _ in ms if r is not None for x in (r if isinstance(r, tuple) else (r,))}
        settings = {"main": flat(main_m),
                    "key1_only": {r for r, _ in key1 if r is not None},
                    "loose_all_same_name": flat(loose)}
        chains = list(csv.DictReader(open(BREACH / f"{box}_chains.csv", encoding="utf-8")))
        c2 = [c for c in chains if int(c["overflowed"]) >= 2 and float(c["people_chain"]) >= 1.0]
        for name, des in settings.items():
            d = lambda s: bool(rows_of(s) & des)
            over_nodes = {o for c in c2 for o in c["overflowed_source_rows"].split(" > ")}
            b1.append(dict(box=box, setting=name, starts=len(chains), starts_designated=sum(d(c["start_source_rows"]) for c in chains),
                           starts_designated_share=round(sum(d(c["start_source_rows"]) for c in chains) / len(chains), 3),
                           chains_2plus_people=len(c2),
                           chain_starts_designated=sum(d(c["start_source_rows"]) for c in c2),
                           chain_starts_designated_share=round(sum(d(c["start_source_rows"]) for c in c2) / len(c2), 3),
                           chain_starts_not_designated=sum(not d(c["start_source_rows"]) for c in c2),
                           chain_starts_not_designated_people_ge_100=sum(not d(c["start_source_rows"]) and float(c["people_chain"]) >= 100 for c in c2),
                           overflowed_nodes=len(over_nodes),
                           overflowed_nodes_not_designated=sum(not d(o) for o in over_nodes)))
            if name == "main":
                for c in c2:
                    if d(c["start_source_rows"]):
                        continue
                    rs = sorted(rows_of(c["start_source_rows"]))
                    cands.append(dict(box=box, start_node=c["start"], start_names=c["start_names"],
                                      source_rows="|".join(map(str, rs)),
                                      municipality=spec[rs[0]]["municipality"] if rs[0] in spec else "",
                                      address="|".join(spec[r]["address"] or "" for r in rs if r in spec),
                                      start_m3=c["start_m3"], start_h_m=c["start_h_m"], overflowed=c["overflowed"],
                                      overflowed_names=c["overflowed_names"],
                                      overflowed_designated=" > ".join("yes" if d(o) else "no"
                                                                       for o in c["overflowed_source_rows"].split(" > ")),
                                      people_single=c["people_single"], people_chain=c["people_chain"], stop=c["stop"]))
    write(OUT / "b0_match.csv", b0)
    write(OUT / "b1.csv", b1)
    write(OUT / "candidates.csv", sorted(cands, key=lambda r: (r["box"], -float(r["people_chain"]))))
    write(RAW.parent / "unmatched.csv", unmatched)
    for r in b0:
        if r["municipality"] == "(all)":
            print(r)
    for r in b1:
        print(r)


if __name__ == "__main__":
    main()
