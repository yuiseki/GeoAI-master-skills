"""Classify the values of polygons for a choropleth, compare classifications, and draw the map with what
a reader needs to read it.

--kind is required: count, rate, level (sequential colours), residual, change (diverging colours, classes
symmetric around --centre), or category (one colour per value, no numeric classes). A palette that does
not fit the kind, or a rainbow palette (rainbow, jet, hsv, ...), stops the run.

Classifications (--method): equal (equal-width classes), quantile (equal counts), jenks (Fisher-Jenks: the
split of the sorted values that minimises the squared deviations within classes; exact, up to 5,000
values), fixed (--thresholds with a meaning of their own, such as a legal limit). --compare prints how
many units change class under other methods; --groups COL prints each group's class shares under bins
shared by all groups and under bins computed per group (the second makes every group look alike).

For a count, the correlation of the value with the polygon's area is printed: big units hold big counts.
Missing values are NoData, drawn apart from 0 and counted.

Output: with --png, the map, and a JSON of the same name with the unit, kind, CRS, source, method, breaks,
counts per class, NoData units and palette (also in the PNG's Description).

Usage:
    uvx --with numpy --with duckdb --with shapely --with matplotlib python classify_map.py TABLE ID VALUE \\
        --kind rate --unit "per 1,000" --method quantile --classes 5 --crs EPSG:6677 --source "census 2020" \\
        [--compare equal jenks] [--groups year] [--thresholds 10 20] [--palette viridis] [--png map.png]
"""

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np

SEQUENTIAL = {"viridis", "cividis", "plasma", "magma", "inferno", "Blues", "Greens", "Greys", "Oranges", "Purples",
              "Reds", "YlOrRd", "YlOrBr", "YlGnBu", "OrRd", "PuBu", "BuGn", "GnBu", "PuRd", "RdPu"}
DIVERGING = {"RdBu", "RdBu_r", "coolwarm", "PiYG", "PRGn", "BrBG", "PuOr", "RdYlBu", "RdYlBu_r", "Spectral"}
CATEGORICAL = {"tab10", "tab20", "Set1", "Set2", "Set3", "Paired", "Dark2", "Accent"}
RAINBOW = {"rainbow", "jet", "hsv", "gist_rainbow", "nipy_spectral", "gist_ncar", "turbo"}
KINDS = {"count": SEQUENTIAL, "rate": SEQUENTIAL, "level": SEQUENTIAL, "residual": DIVERGING, "change": DIVERGING,
         "category": CATEGORICAL}
DEFAULT = {"count": "YlOrRd", "rate": "viridis", "level": "viridis", "residual": "RdBu_r", "change": "RdBu_r",
           "category": "tab10"}


def check_palette(kind, name):
    if name.rstrip("_r") in RAINBOW or name in RAINBOW:
        raise SystemExit(f"{name}: its lightness does not rise with the value and it draws edges that are not in "
                         "the data; use a sequential or diverging palette")
    if name not in KINDS[kind]:
        raise SystemExit(f"{name} does not fit a {kind}; use one of {sorted(KINDS[kind])}")


def fisher_jenks(x, k):
    """Edges [min, upper of class 1, ..., max] of the k-class split minimising within-class squares."""
    v = np.sort(np.asarray(x, float))
    n = len(v)
    if n > 5000:
        raise SystemExit(f"{n} values; exact Fisher-Jenks here is O(k n^2), up to 5,000")
    if k > len(np.unique(v)):
        raise SystemExit(f"{k} classes for {len(np.unique(v))} distinct values")
    s1, s2 = np.r_[0, np.cumsum(v)], np.r_[0, np.cumsum(v * v)]

    def ssd(i, j):  # values i .. j - 1
        m = j - i
        return s2[j] - s2[i] - (s1[j] - s1[i]) ** 2 / m

    cost = np.full((k + 1, n + 1), np.inf)
    back = np.zeros((k + 1, n + 1), int)
    cost[0, 0] = 0
    for c in range(1, k + 1):
        for j in range(c, n + 1):
            best, arg = np.inf, c - 1
            for i in range(c - 1, j):
                val = cost[c - 1, i] + ssd(i, j)
                if val < best:
                    best, arg = val, i
            cost[c, j], back[c, j] = best, arg
    ends, j = [], n
    for c in range(k, 0, -1):
        ends.append(j)
        j = back[c, j]
    return [float(v[0])] + [float(v[e - 1]) for e in sorted(ends)]


def breaks(x, method, k=None, thresholds=None, centre=None):
    x = np.asarray(x, float)
    lo, hi = float(x.min()), float(x.max())
    if method == "equal":
        if centre is not None:
            m = max(abs(lo - centre), abs(hi - centre))
            return list(np.linspace(centre - m, centre + m, k + 1))
        return list(np.linspace(lo, hi, k + 1))
    if method == "quantile":
        return list(np.quantile(x, np.linspace(0, 1, k + 1)))
    if method == "jenks":
        return fisher_jenks(x, k)
    if method == "fixed":
        t = sorted(float(v) for v in thresholds)
        if t[0] <= lo or t[-1] >= hi:
            raise SystemExit(f"thresholds {t} must lie inside the values' range ({lo:g}, {hi:g}); "
                             "otherwise a class is empty")
        return [lo, *t, hi]
    raise SystemExit(f"unknown method {method}")


def assign(x, b):
    """Class 0 .. len(b) - 2; upper edges inclusive."""
    return np.searchsorted(np.asarray(b[1:-1], float), np.asarray(x, float), side="left")


def changed_share(a, b):
    return float(np.mean(np.asarray(a) != np.asarray(b)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("value")
    p.add_argument("--kind", required=True, choices=sorted(KINDS))
    p.add_argument("--unit", required=True)
    p.add_argument("--crs", required=True, help="the CRS of the geometries, for the record")
    p.add_argument("--source", required=True, help="data and version (and date)")
    p.add_argument("--method", choices=["equal", "quantile", "jenks", "fixed"])
    p.add_argument("--classes", type=int, default=5)
    p.add_argument("--thresholds", type=float, nargs="*")
    p.add_argument("--centre", type=float, default=0.0)
    p.add_argument("--compare", nargs="*", default=[])
    p.add_argument("--groups")
    p.add_argument("--palette")
    p.add_argument("--geometry", default="geometry")
    p.add_argument("--png")
    a = p.parse_args()
    palette = a.palette or DEFAULT[a.kind]
    check_palette(a.kind, palette)
    if a.kind == "category" and a.method:
        raise SystemExit("a category is drawn one colour per value; numeric classes (--method) do not apply")
    if a.kind != "category" and not a.method:
        p.error("--method is required for a numeric value")

    import duckdb
    import shapely

    con = duckdb.connect()
    con.sql("install spatial; load spatial;")
    gcol = f', "{a.groups}"' if a.groups else ""
    rows = con.sql(f'select "{a.id}", "{a.value}", ST_AsWKB("{a.geometry}"){gcol} from \'{a.table}\'').fetchall()
    ids = [r[0] for r in rows]
    vals = np.array([np.nan if r[1] is None else float(r[1]) for r in rows])
    geoms = [shapely.from_wkb(bytes(r[2])) for r in rows]
    groups = np.array([str(r[3]) for r in rows]) if a.groups else None
    ok = np.isfinite(vals)
    print(f"units {len(ids)}: with a value {int(ok.sum())}, NoData {int((~ok).sum())}; {a.value} ({a.kind}, {a.unit})")

    if a.kind == "count":
        area = np.array([g.area for g in geoms])
        r = np.corrcoef(vals[ok], area[ok])[0, 1] if ok.sum() > 2 else float("nan")
        print(f"correlation with area: {r:+.2f}. Bigger units hold bigger counts; map a rate or density "
              "(count / area, count / population) unless the count itself is the question")

    centre = a.centre if a.kind in ("residual", "change") else None
    if a.kind == "category":
        cats = np.unique(vals[ok])
        b, cls = list(cats), np.searchsorted(cats, vals[ok])
    else:
        b = breaks(vals[ok], a.method, a.classes, a.thresholds, centre)
        cls = assign(vals[ok], b)
    counts = np.bincount(cls, minlength=len(b) - (0 if a.kind == "category" else 1)).tolist()
    print(f"{a.method or 'category'} breaks: {[round(x, 6) for x in b]}; units per class {counts}")
    for m in a.compare:
        other = assign(vals[ok], breaks(vals[ok], m, a.classes, a.thresholds, centre))
        print(f"units changing class, {a.method} vs {m}: {changed_share(cls, other):.3f}")
    if groups is not None and a.kind != "category":
        print(f"class shares by {a.groups}, bins shared by all groups vs computed per group:")
        for gv in np.unique(groups[ok]):
            m = groups[ok] == gv
            own = assign(vals[ok][m], breaks(vals[ok][m], a.method, a.classes, a.thresholds, centre))
            k = len(b) - 1
            share = lambda c: [round(float(x), 3) for x in np.bincount(c, minlength=k) / len(c)]
            print(f"  {gv}: shared {share(cls[m])}, own {share(own)}")

    if a.png:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch, PathPatch
        from matplotlib.path import Path as MPath

        cmap = plt.get_cmap(palette, len(counts))
        fig, ax = plt.subplots(figsize=(8, 8))
        idx = np.full(len(ids), -1)
        idx[ok] = cls
        for g, c in zip(geoms, idx):
            for poly in getattr(g, "geoms", [g]):
                verts = [np.asarray(poly.exterior.coords)] + [np.asarray(r.coords) for r in poly.interiors]
                codes = []
                for v in verts:
                    codes += [MPath.MOVETO] + [MPath.LINETO] * (len(v) - 2) + [MPath.CLOSEPOLY]
                path = MPath(np.concatenate(verts), codes)
                face = (0.85, 0.85, 0.85) if c < 0 else cmap(int(c))
                ax.add_patch(PathPatch(path, facecolor=face, edgecolor="white", lw=0.3, hatch="//" if c < 0 else None))
        ax.autoscale_view()
        ax.set_aspect("equal")
        ax.set_axis_off()
        if a.kind == "category":
            labels = [f"{v:g} ({n})" for v, n in zip(b, counts)]
        else:
            labels = [f"{b[i]:.4g} to {b[i + 1]:.4g} ({counts[i]})" for i in range(len(counts))]
        handles = [Patch(facecolor=cmap(i), label=lab) for i, lab in enumerate(labels)]
        handles.append(Patch(facecolor=(0.85, 0.85, 0.85), hatch="//", label=f"NoData ({int((~ok).sum())})"))
        ax.legend(handles=handles, title=f"{a.value} ({a.unit})", loc="lower left", fontsize=8)
        caption = f"{a.method or 'category'} classes; CRS {a.crs}; {a.source}"
        ax.set_title(caption, fontsize=8)
        meta = {"value": a.value, "kind": a.kind, "unit": a.unit, "crs": a.crs, "source": a.source,
                "method": a.method or "category", "classes": len(counts), "breaks": b, "units_per_class": counts,
                "nodata_units": int((~ok).sum()), "palette": palette, "made": date.today().isoformat()}
        fig.savefig(a.png, dpi=150, bbox_inches="tight", metadata={"Description": json.dumps(meta)})
        Path(a.png).with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        print(f"wrote {a.png} and {Path(a.png).with_suffix('.json')}")


if __name__ == "__main__":
    main()
