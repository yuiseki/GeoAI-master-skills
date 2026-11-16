"""Check a filter or a labelling step that drops rows: known members, a blind recheck of what was dropped, and the
agreement of two passes. references/filters-and-labels.md says when and why.

    seeds    where each known member (a row the filter must keep) ended up: kept, dropped (the filter is wrong for
             it) or not_in_input (the data or the search never had it, and no filter can bring it back).
             Exit 1 unless every seed is kept.
    sample   a reproducible random sample of the dropped rows (in --before, not in --after), written without the
             columns named in --hide (the earlier decision and its reason), so the recheck reads each row afresh.
             The sample is drawn from the sorted keys, so it does not depend on the row order; at least 20 rows, all
             of them when fewer were dropped. A JSON next to the output records the counts, the seed and the hidden
             columns.
    rescue   the share of the rechecked dropped rows that the recheck would keep, with a Wilson 95% interval, and
             the count that interval implies among all dropped rows (--dropped-total).
    agree    agreement of two passes on the same rows (a 2x2 of keep/drop): the counts, observed agreement,
             Cohen's kappa and PABAK (2 * observed - 1). When keeping is rare, kappa is low even for few
             disagreements; report all of them with the counts, and read the disagreements themselves.

Tables are CSV, TSV or Parquet (read with DuckDB; CSV cells are read as text). Keys are compared as text.

    python3 filter_audit.py seeds  --before all.parquet --after kept.parquet --key id --seeds 123 456 789
    python3 filter_audit.py sample --before all.parquet --after kept.parquet --key id --hide reason --out recheck.csv
    python3 filter_audit.py rescue --labels recheck_labelled.csv --column recheck --positive keep --dropped-total 4021
    python3 filter_audit.py agree  --labels labels.csv --a first --b second --positive keep
"""

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

MIN_SAMPLE = 20


def seed_status(before, after, seeds):
    before, after = set(map(str, before)), set(map(str, after))
    out = []
    for s in map(str, seeds):
        out.append((s, "kept" if s in after else "dropped" if s in before else "not_in_input"))
    return out


def dropped(before, after):
    return sorted(set(map(str, before)) - set(map(str, after)))


def draw_recheck(before, after, n=100, seed=0):
    if n < MIN_SAMPLE:
        raise SystemExit(f"the recheck sample needs at least {MIN_SAMPLE} rows, not {n}: a few rows cannot show a "
                         "rate of wrong drops")
    d = dropped(before, after)
    if len(d) <= n:
        return d
    return sorted(random.Random(seed).sample(d, n))


def agreement(first, second, positive):
    if len(first) != len(second) or not first:
        raise SystemExit(f"agreement needs pairs: {len(first)} and {len(second)} labels")
    p = [(x == positive, y == positive) for x, y in zip(first, second)]
    a = sum(x and y for x, y in p)
    b = sum(x and not y for x, y in p)
    c = sum(y and not x for x, y in p)
    d = sum(not x and not y for x, y in p)
    n = len(p)
    po = (a + d) / n
    pa, pb = (a + b) / n, (a + c) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    kappa = None if pe >= 1 else (po - pe) / (1 - pe)
    return {"both_positive": a, "first_only": b, "second_only": c, "both_negative": d, "n": n,
            "observed": po, "chance": pe, "kappa": kappa, "pabak": 2 * po - 1, "positive": positive}


def wilson(k, n, z=1.96):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [max(0.0, centre - half), min(1.0, centre + half)]


def rescue(labels, positive, dropped_total=None):
    k, n = sum(x == positive for x in labels), len(labels)
    lo, hi = wilson(k, n)
    r = {"rescued": k, "sampled": n, "share": k / n if n else None, "share_95": [lo, hi], "positive": positive}
    if dropped_total is not None:
        r["dropped_total"] = dropped_total
        r["implied_rescued_95"] = [round(lo * dropped_total), round(hi * dropped_total)]
    return r


def read_table(path):
    import duckdb
    p = str(path).replace("'", "''")
    if str(path).lower().endswith(".parquet"):
        rel = duckdb.sql(f"select * from read_parquet('{p}')")
    else:
        rel = duckdb.sql(f"select * from read_csv('{p}', all_varchar = true, header = true)")
    return rel.columns, rel.fetchall()


def _keys(path, key):
    cols, rows = read_table(path)
    if key not in cols:
        raise SystemExit(f"{path} has no column {key!r} (columns: {cols})")
    i = cols.index(key)
    return [str(r[i]) for r in rows]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("seeds", "sample"):
        s = sub.add_parser(name)
        s.add_argument("--before", required=True)
        s.add_argument("--after", required=True)
        s.add_argument("--key", required=True)
    sub.choices["seeds"].add_argument("--seeds", nargs="+", required=True)
    sm = sub.choices["sample"]
    sm.add_argument("--n", type=int, default=100)
    sm.add_argument("--seed", type=int, default=0)
    sm.add_argument("--hide", nargs="*", default=[])
    sm.add_argument("--out", required=True)
    rs = sub.add_parser("rescue")
    rs.add_argument("--labels", required=True)
    rs.add_argument("--column", required=True)
    rs.add_argument("--positive", required=True)
    rs.add_argument("--dropped-total", type=int)
    ag = sub.add_parser("agree")
    ag.add_argument("--labels", required=True)
    ag.add_argument("--a", required=True)
    ag.add_argument("--b", required=True)
    ag.add_argument("--positive", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "seeds":
        st = seed_status(_keys(a.before, a.key), _keys(a.after, a.key), a.seeds)
        for s, status in st:
            print(f"{s}\t{status}")
        bad = [s for s, status in st if status != "kept"]
        print("all seeds kept" if not bad else f"{len(bad)} of {len(st)} seeds not kept")
        sys.exit(1 if bad else 0)
    if a.cmd == "sample":
        cols, rows = read_table(a.before)
        if a.key not in cols:
            raise SystemExit(f"{a.before} has no column {a.key!r}")
        missing = [h for h in a.hide if h not in cols]
        if missing:
            raise SystemExit(f"--hide names columns that are not there: {missing}")
        ki = cols.index(a.key)
        before = [str(r[ki]) for r in rows]
        chosen = set(draw_recheck(before, _keys(a.after, a.key), a.n, a.seed))
        keep = [i for i, c in enumerate(cols) if c not in a.hide]
        out = Path(a.out)
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([cols[i] for i in keep])
            for r in sorted((r for r in rows if str(r[ki]) in chosen), key=lambda r: str(r[ki])):
                w.writerow(["" if r[i] is None else r[i] for i in keep])
        meta = {"before": str(a.before), "after": str(a.after), "key": a.key,
                "dropped": len(dropped(before, _keys(a.after, a.key))), "sampled": len(chosen), "seed": a.seed,
                "hidden": a.hide}
        out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(meta, ensure_ascii=False))
        return
    cols, rows = read_table(a.labels)
    col = lambda name: [str(r[cols.index(name)]) for r in rows]  # noqa: E731
    if a.cmd == "rescue":
        print(json.dumps(rescue(col(a.column), a.positive, a.dropped_total), ensure_ascii=False))
    else:
        print(json.dumps(agreement(col(a.a), col(a.b), a.positive), ensure_ascii=False))


if __name__ == "__main__":
    main()
