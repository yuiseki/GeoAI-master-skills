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

Each unit is outlined in a dark grey (EDGE), so that neighbours of one class stay apart, and labelled with
--label COL (a name column) at a point inside its biggest part; with no --label, up to LABEL_MAX units are
labelled by ID, and --no-labels draws none. Interior rings of zero area (seams left when the polygons were
built from smaller ones) are left out of the drawing: outlined, they look like streaks; their number is printed.

Output: with --png, the map, and a JSON of the same name with the unit, kind, CRS, source, method, breaks,
counts per class, NoData units, palette, label column and font (also in the PNG's Description).

Usage:
    uvx --with numpy --with duckdb --with shapely --with matplotlib python classify_map.py TABLE ID VALUE \\
        --kind rate --unit "per 1,000" --method quantile --classes 5 --crs EPSG:6677 --source "census 2020" \\
        [--compare equal jenks] [--groups year] [--thresholds 10 20] [--palette viridis] [--label name] [--png map.png]
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
    base = name.removesuffix("_r")  # a reversed palette keeps its kind; it only flips which end is dark
    if base in RAINBOW:
        raise SystemExit(f"{name}: its lightness does not rise with the value and it draws edges that are not in "
                         "the data; use a sequential or diverging palette")
    if name not in KINDS[kind] and base not in KINDS[kind]:
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


EDGE = "#404040"   # unit outlines: dark enough to show on the lightest class colour, thin enough not to hide a unit
LABEL_MAX = 50     # with no --label, label units by ID only when there are this few
EDGE_MIN_PX = 6    # with --edges auto, outline units only when their median width is at least this many pixels:
                   # thinner, the outlines merge into a dark mesh that hides the colours


def drop_degenerate_holes(poly, rel=1e-9):
    """poly without the interior rings whose area is at most rel times the polygon's; and how many were dropped."""
    import shapely

    keep = [r for r in poly.interiors if shapely.Polygon(r).area > rel * shapely.Polygon(poly.exterior).area]
    return shapely.Polygon(poly.exterior, keep), len(poly.interiors) - len(keep)


def fmt_break(x):
    """A class edge for the legend: whole numbers with thousands separators from 1,000 up, else 4 significant digits."""
    return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:.4g}"


def label_point(geom):
    """A point inside the biggest part of geom (a centroid can fall outside a bent or holed unit)."""
    part = max(getattr(geom, "geoms", [geom]), key=lambda g: g.area)
    return part.point_on_surface()


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
    p.add_argument("--label", help="column whose values name the units on the map (e.g. name)")
    p.add_argument("--no-labels", action="store_true", help="draw no labels")
    p.add_argument("--title", help="the question the map answers, as its title (else the caption)")
    p.add_argument("--context", help="background areas (GeoParquet or a file ST_Read reads): land, boundaries, names")
    p.add_argument("--context-name", default="name", help="column naming the background areas")
    p.add_argument("--context-where", help="SQL condition selecting the background areas")
    p.add_argument("--context-crs", help="CRS of the background; must equal --crs unless --accept-crs-difference")
    p.add_argument("--context-source", help="background data and version, written under the map")
    p.add_argument("--accept-crs-difference", help="why the background's other CRS does not show at this scale")
    p.add_argument("--highlight", help="CSV with id, group and optionally rank: units outlined by group and numbered")
    p.add_argument("--inset", type=float, nargs=4, metavar=("XMIN", "XMAX", "YMIN", "YMAX"),
                   help="a zoom drawn in a corner (--inset-at), for crowded highlights")
    p.add_argument("--inset-at", default="lower right", choices=["lower right", "lower left", "upper right",
                                                                  "upper left"], help="corner of the map holding the inset")
    p.add_argument("--expect-units", type=int, help="stop unless this many units are drawn (from the analysis)")
    p.add_argument("--edges", choices=["auto", "on", "off"], default="auto",
                   help="unit outlines; auto drops them when units are too small to see between the lines")
    p.add_argument("--font", help="font family for the map's text; by default a Japanese font only when the text needs one")
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
    label_col = None if a.no_labels else a.label
    gcol = f', "{a.groups}"' if a.groups else ""
    lcol = f', "{label_col}"' if label_col else ""
    rows = con.sql(f'select "{a.id}", "{a.value}", ST_AsWKB("{a.geometry}"){gcol}{lcol} '
                   f'from \'{a.table}\'').fetchall()
    ids = [r[0] for r in rows]
    vals = np.array([np.nan if r[1] is None else float(r[1]) for r in rows])
    geoms = [shapely.from_wkb(bytes(r[2])) for r in rows]
    groups = np.array([str(r[3]) for r in rows]) if a.groups else None
    if not a.no_labels and not label_col and len(ids) <= LABEL_MAX:
        label_col = a.id
        print(f"units labelled by {a.id}; give --label with a name column for readable labels, or --no-labels")
    names = None
    if label_col:
        names = ["" if r[-1] is None else str(r[-1]) for r in rows] if lcol else [str(i) for i in ids]
    if a.expect_units is not None and len(ids) != a.expect_units:
        raise SystemExit(f"{len(ids)} units read, expected {a.expect_units}: the table is not the analysis' units")
    areas_note = None
    if a.context:
        if not a.context_crs or not a.context_source:
            raise SystemExit("--context needs --context-crs and --context-source (data and version)")
        from context_map import check_context_crs

        areas_note = check_context_crs(a.crs, a.context_crs, a.accept_crs_difference)
    hl = read_highlights(a.highlight, ids) if a.highlight else None
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
            def share(c, nclasses=k):
                return [round(float(x), 3) for x in np.bincount(c, minlength=nclasses) / len(c)]
            print(f"  {gv}: shared {share(cls[m])}, own {share(own)}")

    if a.png:
        draw_map(a, ids, vals, ok, cls, b, counts, geoms, names, label_col, palette, hl, areas_note)


HIGHLIGHT = ["#8e2675", "#157f9b", "#b45f06", "#000000"]  # outline colours of highlighted groups, in order of appearance


def read_highlights(path, ids):
    """(id, group, rank) rows of a CSV with columns id, group and optionally rank; unknown ids stop the run."""
    import csv

    with open(path, newline="") as fh:
        rows = [(r["id"], r["group"], (r.get("rank") or "").strip()) for r in csv.DictReader(fh)]
    unknown = [i for i, _, _ in rows if i not in set(map(str, ids))]
    if unknown:
        raise SystemExit(f"highlighted ids not among the units: {unknown[:10]}")
    groups = list(dict.fromkeys(g for _, g, _ in rows))
    if len(groups) > len(HIGHLIGHT):
        raise SystemExit(f"{len(groups)} highlight groups; at most {len(HIGHLIGHT)} stay distinguishable")
    return rows, groups


def draw_map(a, ids, vals, ok, cls, b, counts, geoms, names, label_col, palette, hl, crs_note):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shapely
    from matplotlib.patches import Patch, PathPatch
    from matplotlib.path import Path as MPath

    from context_map import (areas_containing, aspect, draw_areas_over, draw_areas_under, label_areas,
                             read_areas, text_overlaps)

    if a.kind == "category":
        labels = [f"{v:g} ({n})" for v, n in zip(b, counts)]
    else:
        labels = [f"{fmt_break(b[i])} to {fmt_break(b[i + 1])} ({counts[i]})" for i in range(len(counts))]
    legend_title = f"{a.value} ({a.unit})"
    caption = f"{a.method or 'category'} classes; CRS {a.crs}; {a.source}"
    if a.context:
        caption += f"; background {a.context_source}"
    xmin, ymin, xmax, ymax = shapely.GeometryCollection(geoms).bounds
    pad = 0.03 * max(xmax - xmin, ymax - ymin)
    view = (xmin - pad, xmax + pad, ymin - pad, ymax + pad)
    areas = read_areas(a.context, a.context_name, a.context_where, shapely.box(view[0] - pad, view[2] - pad,
                       view[1] + pad, view[3] + pad)) if a.context else []
    hl_rows, groups = hl if hl else ([], [])
    title = a.title or caption
    text = " ".join(labels + [legend_title, caption, title, f"NoData ({int((~ok).sum())})"] + (names or [])
                    + [n for n, _ in areas] + groups + [r for _, _, r in hl_rows])
    font = None
    if a.font or not text.isascii():
        # without a Japanese font matplotlib only warns and saves empty boxes: stop before drawing instead
        from cjk_font import use_cjk_font

        font = use_cjk_font(text, a.font)
    cmap = plt.get_cmap(palette, len(counts))
    idx = np.full(len(ids), -1)
    idx[ok] = cls
    by_id = {str(i): g for i, g in zip(ids, geoms)}
    colour = {g: HIGHLIGHT[k] for k, g in enumerate(groups)}

    def draw_units(ax, fontsize, edges):
        seams = 0
        draw_areas_under(ax, areas)
        for g, c in zip(geoms, idx):
            for poly in getattr(g, "geoms", [g]):
                poly, n = drop_degenerate_holes(poly)
                seams += n
                verts = [np.asarray(poly.exterior.coords)] + [np.asarray(r.coords) for r in poly.interiors]
                codes = []
                for v in verts:
                    codes += [MPath.MOVETO] + [MPath.LINETO] * (len(v) - 2) + [MPath.CLOSEPOLY]
                path = MPath(np.concatenate(verts), codes)
                face = (0.85, 0.85, 0.85) if c < 0 else cmap(int(c))
                ax.add_patch(PathPatch(path, facecolor=face, edgecolor=EDGE if edges else face,
                                       lw=0.4 if edges else 0.1, hatch="//" if c < 0 else None, zorder=2))
        draw_areas_over(ax, areas)
        rank_texts = []
        xl, yl = ax.get_xlim(), ax.get_ylim()
        for i, g, rank in hl_rows:
            for poly in getattr(by_id[i], "geoms", [by_id[i]]):
                ax.add_patch(PathPatch(MPath(np.asarray(poly.exterior.coords)), facecolor="none",
                                       edgecolor=colour[g], lw=2.0, zorder=7))
            bx = by_id[i].bounds
            if rank and xl[0] <= bx[2] <= xl[1] and yl[0] <= bx[3] <= yl[1]:
                rank_texts.append((i, ax.annotate(rank, (bx[2], bx[3]), xytext=(2, 2), textcoords="offset points",
                                                  fontsize=fontsize, color=colour[g], fontweight="bold", zorder=8,
                                                  annotation_clip=True,
                                                  bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none",
                                                        "alpha": 0.85})))
        ax.set_xticks([])
        ax.set_yticks([])
        return seams, rank_texts

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(view[0], view[1])
    ax.set_ylim(view[2], view[3])
    ax.set_aspect(aspect(a.crs, view[2], view[3]))
    edges = a.edges == "on"
    if a.edges == "auto":
        fig.canvas.draw()
        to_px = ax.transData.transform
        widths = [abs(to_px((g.bounds[2], 0))[0] - to_px((g.bounds[0], 0))[0]) for g in geoms]
        edges = bool(np.median(widths) >= EDGE_MIN_PX)
        if not edges:
            print(f"unit outlines left out: units are {np.median(widths):.1f} px wide (median); --edges on to draw them")
    seams, rank_texts = draw_units(ax, 7.5, edges)
    main_ranks = [t for _, t in rank_texts]
    if seams:
        print(f"left out {seams} interior rings of zero area (seams, not holes)")
    unit_texts = []
    if names:
        from matplotlib import patheffects

        halo = [patheffects.withStroke(linewidth=2, foreground="white")]
        for g, nm in zip(geoms, names):
            pt = label_point(g)
            unit_texts.append(ax.text(pt.x, pt.y, nm, ha="center", va="center", fontsize=6, path_effects=halo,
                                      zorder=6))
    area_texts = label_areas(ax, areas, view)
    hidden = []
    if a.inset:
        x0, x1, y0, y1 = a.inset
        corner = {"lower right": [0.64, 0.03], "lower left": [0.02, 0.03], "upper right": [0.64, 0.63],
                  "upper left": [0.02, 0.63]}[a.inset_at]
        inset = ax.inset_axes([*corner, 0.34, 0.34])
        inset.set_zorder(10)
        inset.set_xlim(x0, x1)
        inset.set_ylim(y0, y1)
        inset.set_adjustable("datalim")
        inset.set_aspect(aspect(a.crs, y0, y1))
        _, inset_texts = draw_units(inset, 9, True)
        ax.indicate_inset_zoom(inset, edgecolor="#333333")
        rank_texts += inset_texts
        # a rank whose unit lies inside the zoom is read in the inset; on the main map it may crowd its neighbours
        zoomed = [t for i, t in rank_texts[:len(main_ranks)]
                  if x0 <= label_point(by_id[i]).x <= x1 and y0 <= label_point(by_id[i]).y <= y1]
    handles = [Patch(facecolor=cmap(i), edgecolor=EDGE, label=lab) for i, lab in enumerate(labels)]
    handles.append(Patch(facecolor=(0.85, 0.85, 0.85), hatch="//", label=f"NoData ({int((~ok).sum())})"))
    for g in groups:
        n = sum(1 for _, gg, _ in hl_rows if gg == g)
        handles.append(Patch(facecolor="none", edgecolor=colour[g], lw=2.0, label=f"{g} ({n})"))
    leg = ax.legend(handles=handles, title=legend_title, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    ax.set_title(title, fontsize=11 if a.title else 8, loc="left")
    if a.title:
        ax.text(0, -0.01, caption, transform=ax.transAxes, fontsize=7, color="#444444", va="top")
    if a.inset:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        box = inset.get_window_extent(r)
        for i, g, rank in hl_rows:
            p = label_point(by_id[i])
            inside = x0 <= p.x <= x1 and y0 <= p.y <= y1
            if not inside and box.contains(*ax.transData.transform((p.x, p.y))):
                hidden.append(i)
        if hidden:
            print(f"the inset hides highlighted units {hidden}; move the inset or widen it to hold them")
        # texts of the main map under the inset are covered, not overlapping: they are counted as hidden
        under = [t for t in unit_texts + area_texts + main_ranks if box.overlaps(t.get_window_extent(r))]
    else:
        under, zoomed = [], []
    texts = [t for t in unit_texts + area_texts + [t for _, t in rank_texts] if t not in under and t not in zoomed]
    overlaps = text_overlaps(fig, texts, [leg])
    if overlaps:
        print(f"{len(overlaps)} overlapping texts (first ones: {overlaps[:5]}); open the PNG, then move, drop or "
              "zoom into them (--inset)")
    meta = {"value": a.value, "kind": a.kind, "unit": a.unit, "crs": a.crs, "source": a.source,
            "method": a.method or "category", "classes": len(counts), "breaks": b, "units_per_class": counts,
            "nodata_units": int((~ok).sum()), "palette": palette, "boundary": EDGE, "labels": label_col,
            "labelled_units": len(names) if names else 0, "zero_area_rings_left_out": seams, "font": font,
            "unit_edges": edges, "covered_by_inset": [t.get_text() for t in under],
            "zoomed_in_inset": [t.get_text() for t in zoomed], "inset_at": a.inset_at,
            "title": a.title, "aspect": aspect(a.crs, view[2], view[3]), "legend": "outside",
            "text_overlaps": [list(o) for o in overlaps], "inset": a.inset, "hidden_by_inset": hidden,
            "made": date.today().isoformat()}
    if a.context:
        meta["context"] = {"path": a.context, "name": a.context_name, "where": a.context_where,
                           "source": a.context_source, "crs": a.context_crs, "crs_difference": crs_note,
                           "areas": len(areas), "labelled": [t.get_text() for t in area_texts]}
    if hl:
        meta["highlight"] = {"path": a.highlight, "groups": {g: sum(1 for _, gg, _ in hl_rows if gg == g)
                                                            for g in groups}}
        out = Path(a.png).with_name(Path(a.png).stem + "-highlights.csv")
        with out.open("w") as fh:
            fh.write("id,group,rank,area\n")
            for i, g, rank in hl_rows:
                fh.write(f"{i},{g},{rank},{areas_containing(label_point(by_id[i]), areas)}\n")
    fig.savefig(a.png, dpi=170, bbox_inches="tight", metadata={"Description": json.dumps(meta)})
    plt.close(fig)
    Path(a.png).with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {a.png} and {Path(a.png).with_suffix('.json')}")


if __name__ == "__main__":
    main()
