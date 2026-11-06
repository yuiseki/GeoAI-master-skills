"""B0 and B1 of EXPERIMENT_PLAN.md: the widened chains (outputs/) against tameike-cascade-breach's main setting.
Starts are paired by their ledger rows. Writes outputs/b0.csv, outputs/b1.csv and outputs/b0_differences.csv.

  python3 scripts/compare.py
"""

import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "outputs"
BREACH = PROJECT.parent / "tameike-cascade-breach/outputs"
LEAVES = "flow leaves the area or reaches no pond"


def load(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    b0, b1, diffs = [], [], []
    summary_w = load(OUT / "summary.csv")
    summary_o = load(BREACH / "summary.csv")
    for box in ("kagawa", "fukuyama", "awaji"):
        old = {r["start_source_rows"]: r for r in load(BREACH / f"{box}_chains.csv")}
        new = {r["start_source_rows"]: r for r in load(OUT / f"{box}_chains.csv")}
        both = [k for k in old if k in new]
        checked = [k for k in both if old[k]["stop"] != LEAVES]
        same = [k for k in checked if old[k]["overflowed_source_rows"] == new[k]["overflowed_source_rows"]]
        for k in checked:
            if k not in same:
                diffs.append(dict(box=box, start_source_rows=k, start_names=old[k]["start_names"],
                                  old_overflowed=old[k]["overflowed_names"], old_stop=old[k]["stop"],
                                  new_overflowed=new[k]["overflowed_names"], new_stop=new[k]["stop"]))
        b0.append(dict(box=box, starts_old=len(old), starts_new=len(new), starts_in_both=len(both),
                       starts_only_new=sum(k not in old for k in new), starts_only_old=sum(k not in new for k in old),
                       checked=len(checked), same=len(same), same_share=round(len(same) / len(checked), 4)))
        c2 = lambda rows: [r for r in rows if int(r["overflowed"]) >= 2 and float(r["people_chain"]) >= 1.0]
        o2, n2 = c2(old.values()), c2(new.values())
        rng = lambda s: [int(r["chains_2plus_people"]) for r in s if r["box"] == box]
        b1.append(dict(box=box, chains_2plus_people_old=len(o2), chains_2plus_people_new=len(n2),
                       old_ending_at_edge=sum(r["end_at_edge"] == "True" for r in o2),
                       new_ending_at_edge=sum(r["end_at_edge"] == "True" for r in n2),
                       new_ending_at_edge_share=round(sum(r["end_at_edge"] == "True" for r in n2) / len(n2), 3),
                       max_overflowed_old=max(int(r["overflowed"]) for r in o2),
                       max_overflowed_new=max(int(r["overflowed"]) for r in n2),
                       old_chains_longer_now=sum(int(new[k]["overflowed"]) > int(old[k]["overflowed"]) for k in both
                                                 if int(old[k]["overflowed"]) >= 1),
                       old_chains_shorter_now=sum(int(new[k]["overflowed"]) < int(old[k]["overflowed"]) for k in both),
                       variants_min_new=min(rng(summary_w)), variants_max_new=max(rng(summary_w)),
                       variants_min_old=min(rng(summary_o)), variants_max_old=max(rng(summary_o))))
    write(OUT / "b0.csv", b0)
    write(OUT / "b1.csv", b1)
    write(OUT / "b0_differences.csv", diffs or [dict(box="", start_source_rows="", start_names="", old_overflowed="",
                                                       old_stop="", new_overflowed="", new_stop="")])
    for r in b0 + b1:
        print(r)


if __name__ == "__main__":
    main()
