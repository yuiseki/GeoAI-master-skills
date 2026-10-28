"""Assign the legends of 現存植生図2024 (Akita) to the four beech/oak categories, by legend code only.

Writes outputs/vegetation_mapping.csv: every legend present in Akita, with its category ('none' when not
counted) and the reason. Names are never matched by substring; the expected name of each assigned code is
checked so that a code that means something else stops the run.

    uvx --with pandas python mapping.py LEGEND_AKITA_TSV OUT_CSV
"""

import csv
import sys

# code: (category, expected name, reason). A name 'X－Y' is read as Y the main (dominant) tree and X a
# companion or differential species, the usual naming of plant-sociological units.
ASSIGNED = {
    "110100": ("beech", "チシマザサ－ブナ群団", "自然林のブナ林 (ブナが主、チシマザサが林床)"),
    "110103": ("beech", "スギ－ブナ群落", "スギを交えるブナ林 (ブナが主)"),
    "220104": ("beech", "ブナ二次林", "二次林のブナ林"),
    "220100": ("beech_mizunara", "ブナ－ミズナラ群落", "ブナとミズナラの二次林。独立の category"),
    "110501": ("mizunara", "ホツツジ－ミズナラ群集", "自然林のミズナラ林 (ミズナラが主)"),
    "220101": ("mizunara", "スギ－ミズナラ群落", "スギを交えるミズナラ林 (ミズナラが主)"),
    "220103": ("mizunara", "オオバクロモジ－ミズナラ群集", "二次林のミズナラ林 (ミズナラが主)"),
    "221100": ("mizunara", "ミズナラ群落（V）", "二次林のミズナラ林"),
    "220500": ("konara", "コナラ群落（V）", "二次林のコナラ林"),
    "220501": ("konara", "オクチョウジザクラ－コナラ群集", "二次林のコナラ林 (コナラが主)"),
}
CATEGORY = {k: v[0] for k, v in ASSIGNED.items()}
EXCLUDED = {
    "190100": "ミヤマナラは多雪の尾根の低木のナラで、ここで数えるナラ類の林ではない (名前にナラを含むが入れない)",
    "110401": "カシワの群落。ナラ属だが 4 つの category に入らない",
    "110402": "カシワの群落。ナラ属だが 4 つの category に入らない",
    "220200": "カシワの群落。ナラ属だが 4 つの category に入らない",
}
OTHER = "ブナ・ナラ類 (ブナ、ミズナラ、コナラ) が主の群落ではない"


def table(legends, check_all=True):
    """legends: [(code, name, 植生区分)] -> rows in code order."""
    rows = []
    for code, name, kubun in sorted(legends):
        if code in ASSIGNED:
            cat, expect, reason = ASSIGNED[code]
            if name != expect:
                raise ValueError(f"legend {code} is {name!r}, expected {expect!r}")
        else:
            cat, reason = "none", EXCLUDED.get(code, OTHER)
        rows.append({"凡例コード": code, "原凡例名": name, "植生区分": kubun, "category": cat, "reason": reason})
    missing = set(ASSIGNED) - {r["凡例コード"] for r in rows}
    if check_all and missing:
        raise ValueError(f"assigned codes not in the legend list: {sorted(missing)}")
    return rows


def main():
    src, out = sys.argv[1:3]
    with open(src, encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        legends = [(x["凡例コード"], x["凡例名"], x["植生区分"]) for x in r]
    rows = table(legends)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    n = {c: sum(r["category"] == c for r in rows) for c in ("beech", "beech_mizunara", "mizunara", "konara", "none")}
    print(len(rows), n)


if __name__ == "__main__":
    main()
