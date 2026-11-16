"""Let the machine rank, look only at the top, and still say what the ranking missed.

Looking at every view, box or patch takes the eye (a person's or a model's) longer than the work allows: the Paris
run spent its two hours there and left no report. The model's score can rank the items so that the eye looks at the
top of the list first. But the top alone tells only how many of the top are right, not how many positives the
ranking put lower down. So the budget of looks is split, before anything is looked at:

    top    the highest-scored items (budget * --top-share), all of them looked at
    rest   a random sample of all the others (the rest of the budget), drawn with a fixed seed; the items are first
           sorted by score and id, so the plan does not depend on the row order

estimate adds the positives found in the top to the rest's share (Wilson 95%) times the size of the rest, and says
which part of that total the top caught. A plan whose top takes the whole budget stops: it could not say what the
ranking missed. To estimate a rate over all items (the share of poles that lean), draw a uniform sample instead
(references/validation-and-gaps.md); this plan is for finding the positives with few looks.

    python3 review_plan.py plan scores.csv --id box --score score --budget 60 [--top-share 0.5] [--seed 0] --out review.csv
    ... fill the label column (the look) ...
    python3 review_plan.py estimate review.csv --positive yes
"""

import argparse
import csv
import json
import math
import random
import sys


def plan(ids, scores, budget, top_share=0.5, seed=0):
    items = sorted(zip(map(str, ids), map(float, scores)), key=lambda t: (-t[1], t[0]))
    if budget >= len(items):
        return [{"id": i, "score": s, "stratum": "top", "stratum_size": len(items)} for i, s in items]
    k = round(budget * top_share)
    if budget - k < 1:
        raise SystemExit("the top takes the whole budget: leave some looks for a random sample of the rest, or "
                         "nothing can be said about what the ranking missed")
    top, rest = items[:k], items[k:]
    rng = random.Random(seed)
    chosen = sorted(rng.sample([i for i, _ in rest], budget - k))
    score = dict(rest)
    return ([{"id": i, "score": s, "stratum": "top", "stratum_size": len(top)} for i, s in top]
            + [{"id": i, "score": score[i], "stratum": "rest", "stratum_size": len(rest)} for i in chosen])


def wilson(k, n, z=1.96):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [max(0.0, centre - half), min(1.0, centre + half)]


def estimate(rows, positive):
    unlabelled = [r["id"] for r in rows if str(r.get("label", "")).strip() == ""]
    if unlabelled:
        raise SystemExit(f"{len(unlabelled)} items have no label yet (first: {unlabelled[0]})")
    top = [r for r in rows if r["stratum"] == "top"]
    rest = [r for r in rows if r["stratum"] == "rest"]
    tp = sum(r["label"] == positive for r in top)
    k, n = sum(r["label"] == positive for r in rest), len(rest)
    size = int(rest[0]["stratum_size"]) if rest else 0
    share = k / n if n else 0.0
    lo, hi = wilson(k, n) if n else [0.0, 0.0]
    total = tp + size * share
    return {"top_looked": len(top), "top_positives": tp, "rest_size": size, "rest_sampled": n,
            "rest_positives_sampled": k, "rest_share": share, "rest_share_95": [lo, hi], "total_estimate": total,
            "total_95": [tp + size * lo, tp + size * hi], "top_catches": tp / total if total else None,
            "positive": positive}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("scores")
    p.add_argument("--id", required=True)
    p.add_argument("--score", required=True)
    p.add_argument("--budget", type=int, required=True, help="how many items the eye can look at")
    p.add_argument("--top-share", type=float, default=0.5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    e = sub.add_parser("estimate")
    e.add_argument("review")
    e.add_argument("--positive", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        with open(a.scores, newline="", encoding="utf-8") as f:
            src = list(csv.DictReader(f))
        rows = plan([r[a.id] for r in src], [r[a.score] for r in src], a.budget, a.top_share, a.seed)
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "score", "stratum", "stratum_size", "label"])
            w.writeheader()
            w.writerows(dict(r, label="") for r in rows)
        print(json.dumps({"items": len(src), "budget": a.budget, "top": sum(r["stratum"] == "top" for r in rows),
                          "rest_sampled": sum(r["stratum"] == "rest" for r in rows), "seed": a.seed}))
        return
    with open(a.review, newline="", encoding="utf-8") as f:
        print(json.dumps(estimate(list(csv.DictReader(f)), a.positive), ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
