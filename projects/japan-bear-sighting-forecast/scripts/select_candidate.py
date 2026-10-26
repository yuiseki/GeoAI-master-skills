"""Pick the candidate to freeze (plan block B2): the lowest MAE averaged over the horizons.

Candidates are given in order of fewer features first; a tie goes to the earlier one.

Usage:
    python3 select_candidate.py SCORES.json OUT.csv glm hgb hier_hgb glm_nb hgb_nb [--horizons 1 2 4]
"""

import argparse
import json


def select(scores, candidates, horizons):
    table = {c: sum(scores[f"{c}|h{h}"]["mae"] for h in horizons) / len(horizons) for c in candidates}
    best = min(candidates, key=lambda c: (table[c], candidates.index(c)))
    return table, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scores")
    ap.add_argument("out")
    ap.add_argument("candidates", nargs="+")
    ap.add_argument("--horizons", type=int, nargs="+", default=[1, 2, 4])
    a = ap.parse_args()
    sc = json.load(open(a.scores))
    table, best = select(sc, a.candidates, a.horizons)
    ref = {m: sum(sc[f"{m}|h{h}"]["mae"] for h in a.horizons) / len(a.horizons) for m in ("naive", "mean_short")}
    with open(a.out, "w") as f:
        f.write("model,mean_mae_over_horizons,role\n")
        for c in sorted(table, key=table.get):
            f.write(f"{c},{table[c]:.3f},{'frozen' if c == best else 'candidate'}\n")
        for m, v in ref.items():
            f.write(f"{m},{v:.3f},baseline\n")
    print(open(a.out).read())


if __name__ == "__main__":
    main()
