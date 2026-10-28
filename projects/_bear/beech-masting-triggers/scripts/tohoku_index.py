"""The Tohoku Regional Forest Office's beech flowering and fruiting index by prefecture and year, read from the
table "年度別ブナ開花状況並びに結実状況" in its press releases (PDF), and checked three ways: two releases must
agree on every year they share, the FY2026 rows must match the index recomputed from the release's own counts of
sites, and the parsed table must have one value per prefecture, stage and year where the PDF has one.

The index is (5 × 全体 + 3 × 部分 + 1 × 一部) / sites, 0 to 5; classes: 豊作 3.5 or more, 並作 2.0 to 3.5, 凶作
1.0 to 2.0, 大凶作 under 1.0 (皆無 until FY2016). 開花時 is the survey in early summer, 結実時 in autumn.

From repository root:
    uvx --with pdfplumber python projects/_bear/beech-masting-triggers/scripts/tohoku_index.py \
      artifacts/_bear/beech-masting-triggers/raw projects/_bear/beech-masting-triggers/outputs
"""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

PAGE = "https://www.rinya.maff.go.jp/tohoku/sidou/buna.html"
PDFS = {  # release: what it holds
    "buna-57.pdf": "令和8年度の結実状況 (2026-10-06)。表は 1989〜2026 年度",
    "buna-55.pdf": "令和7年度の結実状況 (2025-11-06)。表は 1989〜2025 年度",
    "buna-56.pdf": "令和8年度の開花状況 (2026-07-07)。県別の箇所数",
}
PREFS = ["青森県", "岩手県", "宮城県", "秋田県", "山形県"]
STAGES = ["flowering", "fruiting"]  # 開花時, 結実時: the columns alternate in this order under each prefecture
ENTRY = re.compile(r"(大凶作|凶作|並作|豊作|皆無)（(\d)\.(\d)）")
YEAR = re.compile(r"^(19[89]\d|20[0-4]\d)$")


def norm(s):
    return unicodedata.normalize("NFKC", s).replace(" ", "")


def entries(chars):
    """(x, top, class, index) for each entry, from the page's characters (pdfplumber chars: text, x0, top).

    Characters are grouped into lines by their top (a line's characters can differ by a point), joined in x order without spaces (the PDF splits 3.4 into
    "3 . 4" and words into pieces), and the entry starts at the x of its first character.
    """
    lines = []  # characters whose tops are within 2 pt of the previous one share a line
    for c in sorted(chars, key=lambda c: c["top"]):
        if lines and c["top"] - lines[-1][-1]["top"] <= 2:
            lines[-1].append(c)
        else:
            lines.append([c])
    out = []
    for cs in lines:
        top = round(sum(c["top"] for c in cs) / len(cs), 1)
        cs = sorted((c for c in cs if c["text"].strip()), key=lambda c: c["x0"])
        text, xs = "", []
        for c in cs:
            t = unicodedata.normalize("NFKC", c["text"])
            text += t
            xs += [c["x0"]] * len(t)
        text = text.replace("(", "（").replace(")", "）")
        for m in ENTRY.finditer(text):
            out.append((xs[m.start()], top, m.group(1), int(m.group(2)) + int(m.group(3)) / 10))
    return out


def years(words):
    """(top, year) of the year labels (words that are a 4-digit year after normalising)."""
    return [(w["top"], int(norm(w["text"]))) for w in words if YEAR.match(norm(w["text"]))]


def column_centres(words):
    """x of the ten columns: the 開 and 結 of the header (開花時, 結実時) in x order."""
    heads = sorted(w["x0"] for w in words if norm(w["text"])[:1] in ("開", "結") and w["top"] < 100)
    if len(heads) != 10:
        raise ValueError(f"expected 10 column heads, found {len(heads)}")
    return heads


def table(chars, words, tol=10):
    """Rows (year, pref, stage, index, class) of the table."""
    cols = column_centres(words)
    ys = years(words)
    rows = {}
    for x, top, cls, idx in entries(chars):
        col = min(range(10), key=lambda i: abs(cols[i] - x))
        if abs(cols[col] - x) > 15:
            raise ValueError(f"entry at x {x} is not under a column")
        near = [(abs(t - top), y) for t, y in ys if abs(t - top) <= tol]
        if not near:
            raise ValueError(f"entry at top {top} has no year")
        year = min(near)[1]
        key = (year, PREFS[col // 2], STAGES[col % 2])
        if key in rows:
            raise ValueError(f"two entries for {key}")
        rows[key] = (idx, cls)
    return rows


def at_boundary(idx, cls):
    """The printed index sits on a class threshold and the class is the one below: the unrounded index was just
    under it (FY2011 山形県 結実時 is printed 凶作 (2.0))."""
    below = {3.5: "並作", 2.0: "凶作", 1.0: ("大凶作", "皆無")}.get(idx)
    return below is not None and (cls in below if isinstance(below, tuple) else cls == below)


def check_class(idx, cls):
    want = "豊作" if idx >= 3.5 else "並作" if idx >= 2.0 else "凶作" if idx >= 1.0 else ("大凶作", "皆無")
    return cls in want if isinstance(want, tuple) else cls == want


def release_counts(text):
    """{pref: (全体, 部分, 一部, 無し, 計, 指数)} from a release's table of counts of sites."""
    out = {}
    for line in text.splitlines():
        s = unicodedata.normalize("NFKC", line)
        m = re.match(r"\s*(青森県|岩手県|宮城県|秋田県|山形県)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d\.\d)", s)
        if m:
            v = [int(g) for g in m.groups()[1:6]]
            out[m.group(1)] = (*v, float(m.group(7)))
    return out


def index_from_counts(full, part, few, none, total):
    if full + part + few + none != total:
        raise ValueError("counts do not add up")
    return (5 * full + 3 * part + few) / total


def read_pdf(path):
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            words = p.extract_words(x_tolerance=1.5)
            if "年度別" in "".join(w["text"] for w in words):
                return table(p.chars, words)
    raise ValueError(f"no table in {path}")


def main():
    import pdfplumber
    import urllib.request

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("raw", type=Path)
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    a.raw.mkdir(parents=True, exist_ok=True)
    meta = {}
    for name, what in PDFS.items():
        p = a.raw / name
        if not p.exists():
            urllib.request.urlretrieve(f"https://www.rinya.maff.go.jp/tohoku/sidou/attach/pdf/{name}", p)
        meta[name] = {"what": what, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}

    new, old = read_pdf(a.raw / "buna-57.pdf"), read_pdf(a.raw / "buna-55.pdf")
    shared = sorted(set(new) & set(old))
    differ = [k for k in shared if new[k] != old[k]]
    only_old = sorted(set(old) - set(new))
    off_class = [k for k, (i, c) in new.items() if not check_class(i, c)]
    bad_class = [k for k in off_class if not at_boundary(*new[k])]
    with pdfplumber.open(a.raw / "buna-57.pdf") as pdf:
        fruit26 = release_counts(pdf.pages[0].extract_text())
    with pdfplumber.open(a.raw / "buna-56.pdf") as pdf:
        flower26 = release_counts(pdf.pages[0].extract_text())
    recomputed = {}
    for stage, counts in (("fruiting", fruit26), ("flowering", flower26)):
        for pref, (f, pa, fe, no, tot, idx) in counts.items():
            r = index_from_counts(f, pa, fe, no, tot)
            recomputed[f"{pref} {stage}"] = {"recomputed": round(r, 3), "printed": idx, "table": new[(2026, pref, stage)][0]}
            if abs(round(r, 1) - idx) > 0.051 or new[(2026, pref, stage)][0] != idx:
                raise ValueError(f"FY2026 {pref} {stage}: recomputed {r:.3f}, printed {idx}, table {new[(2026, pref, stage)][0]}")
    if differ or only_old or bad_class or len(fruit26) != 5 or len(flower26) != 5:
        raise ValueError(f"checks failed: differ {differ[:5]} only_old {only_old[:5]} class {bad_class[:5]}")

    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "tohoku_beech_index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "pref", "stage", "index", "class"])
        for (y, pref, st), (idx, cls) in sorted(new.items(), key=lambda kv: (kv[0][0], PREFS.index(kv[0][1]), kv[0][2])):
            w.writerow([y, pref, st, f"{idx:.1f}", cls])
    missing = [f"{y} {p} {s}" for y in range(1989, 2027) for p in PREFS for s in STAGES if (y, p, s) not in new]
    prov = {"derived": "table transcribed from PDF; values as printed (index to 0.1)",
            "source": PAGE, "licence": "公共データ利用規約 (第1.0版) (PDL1.0)。出典: 東北森林管理局ウェブサイト",
            "retrieved": "2026-10-28", "pdfs": meta, "script": "projects/_bear/beech-masting-triggers/scripts/tohoku_index.py",
            "rows": len(new), "years": [min(k[0] for k in new), max(k[0] for k in new)],
            "missing_cells": missing,
            "class_below_printed_index_at_threshold": [f"{k[0]} {k[1]} {k[2]} {new[k][1]} ({new[k][0]})" for k in off_class], "shared_with_previous_release": len(shared), "differences": len(differ),
            "fy2026_recomputed_from_counts": recomputed}
    (a.out / "tohoku_beech_index.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(len(new), "rows;", len(missing), "missing;", len(shared), "shared, 0 differ", flush=True)


if __name__ == "__main__":
    main()
