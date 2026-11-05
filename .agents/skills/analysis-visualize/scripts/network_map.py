"""Draw a network (edges as lines, optional point layers) with the edges coloured and thickened by an analysed value.

The edges are the figure: no basemap is drawn, so the structure of the network carries the place. One value
sets both the colour and the width of an edge, by explicit classes (--bins, upper-inclusive edges, the first
class starting above 0). Edges with value 0 are drawn as the thin base network; edges with no value (NULL) are
drawn dotted and counted apart from 0. A negative value, or one above the last bin, stops the run.

--theme light (default) or dark. On either, the high class must contrast more with the background than the low
class (CIELAB lightness), so that the busiest edges stand out: YlOrRd on a dark background, or magma on a
light one, stops the run. Rainbow palettes stop the run.

--highlight COL marks edges where COL is true (a cut bridge, a bottleneck) with an outline, and --label-col
names them. --points "path,label,marker,colour" (repeatable) adds point layers from a CSV or Parquet with x and
y columns in the same CRS. Overlapping labels are counted and recorded.

Output: the PNG, and a JSON of the same name with the question, source, CRS, bins, counts per class, NoData and
zero edges, palette, theme, point layers, highlighted edges, labels, text overlaps and font.

Usage:
    uvx --with numpy --with duckdb --with shapely --with matplotlib --with pyarrow --with pandas python network_map.py EDGES \\
        --crs EPSG:6677 --source "OSM 2026-08-31" --question "..." --value n --value-label "..." --unit "..." \\
        --bins 1 10 100 [--geometry geometry] [--palette YlOrRd] [--theme light|dark] [--width-range 0.4 3.5] \\
        [--highlight COL --highlight-label "..." --label-col name] [--points "pts.csv,label,^,#1f6fb2"] \\
        [--view XMIN YMIN XMAX YMAX] [--title "..."] [--note "..."] --png map.png
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

GEOGRAPHIC = {"EPSG:4326", "OGC:CRS84", "EPSG:4612", "EPSG:6668", "CRS84"}
RAINBOW = {"rainbow", "jet", "hsv", "gist_rainbow", "nipy_spectral", "gist_ncar", "turbo"}
THEMES = {
    "light": dict(bg="#ffffff", base="#c8c8c8", nodata="#9a9a9a", text="#222222", outline="#000000"),
    "dark": dict(bg="#0b0b0e", base="#3a3a40", nodata="#6a6a70", text="#eeeeee", outline="#ffffff"),
}
DEFAULT_PALETTE = {"light": "YlOrRd", "dark": "magma"}
LABEL_OFFSETS = [(5, 5), (-5, 5), (5, -5), (-5, -5), (12, 14), (-12, 14), (12, -14), (-12, -14)]


def aspect(crs, ymin, ymax):
    """The y / x display ratio: 1 / cos(mid latitude) for longitude and latitude, 1 otherwise."""
    if crs.upper() in GEOGRAPHIC:
        return 1 / math.cos(math.radians((ymin + ymax) / 2))
    return 1.0


def lightness(rgb):
    """CIELAB L* of an sRGB colour (0..1)."""
    c = np.asarray(rgb[:3], float)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    y = lin @ np.array([0.2126, 0.7152, 0.0722])
    f = y ** (1 / 3) if y > (6 / 29) ** 3 else y / (3 * (6 / 29) ** 2) + 4 / 29
    return 116 * f - 16


def palette_colours(name, k):
    import matplotlib
    cmap = matplotlib.colormaps[name]
    # avoid the palest end, which disappears into a light background (and the darkest into a dark one)
    return [cmap(x) for x in np.linspace(0.25, 1.0, k)]


def palette_contrast_ok(name, theme):
    import matplotlib.colors as mc
    lo, hi = palette_colours(name, 2)
    bg = lightness(mc.to_rgb(THEMES[theme]["bg"]))
    return abs(lightness(hi) - bg) > abs(lightness(lo) - bg)


def class_widths(k, width_range):
    a, b = width_range
    return list(np.linspace(a, b, k)) if k > 1 else [b]


def classify(values, bins):
    """-1 for 0, -2 for missing, else the class index of (0, b0], (b0, b1], ... Stops on bad values."""
    v = np.asarray(values, float)
    nan = np.isnan(v)
    if (v[~nan] < 0).any():
        raise SystemExit(f"{int((v[~nan] < 0).sum())} negative values: this map draws non-negative amounts")
    if (v[~nan] > bins[-1]).any():
        raise SystemExit(f"{int((v[~nan] > bins[-1]).sum())} values above the last bin {bins[-1]}")
    cls = np.searchsorted(np.asarray(bins, float), v, side="left")
    cls = np.where(v == 0, -1, cls)
    cls = np.where(nan, -2, cls)
    return cls


def read_edges(path, geometry, cols):
    import duckdb
    import shapely
    c = duckdb.connect()
    c.execute("install spatial; load spatial")
    sel = ", ".join(f'"{x}"' for x in cols if x)
    q = f"""select {sel + ',' if sel else ''} st_aswkb("{geometry}") wkb from '{path}'"""
    df = c.execute(q).df()
    geoms = shapely.from_wkb(df.pop("wkb").map(bytes).values)
    return df, geoms


def read_points(path):
    import duckdb
    rows = duckdb.connect().execute(f"select x, y from '{path}'").fetchall()
    return np.array(rows, float).reshape(-1, 2)


def point_overlaps(fig, ax, texts, layers, pad_px=4.0):
    """(text, layer label) pairs where a point of the layer lies inside the text's drawn box (padded by the
    marker's radius). A scatter's own window extent covers all its points, so it cannot be used as one mark."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    found = []
    for t in texts:
        if not (t.get_visible() and t.get_text()):
            continue
        bb = t.get_window_extent(r).padded(pad_px)
        for label, xy in layers:
            d = ax.transData.transform(xy) if len(xy) else np.empty((0, 2))
            inside = (d[:, 0] >= bb.x0) & (d[:, 0] <= bb.x1) & (d[:, 1] >= bb.y0) & (d[:, 1] <= bb.y1)
            if inside.any():
                found.append((t.get_text(), label))
    return found


def segments(geoms):
    """Line coordinate arrays of each geometry (a MultiLineString gives several)."""
    out = []
    for g in geoms:
        parts = g.geoms if g.geom_type.startswith("Multi") else [g]
        out.append([np.asarray(p.coords)[:, :2] for p in parts])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edges")
    ap.add_argument("--geometry", default="geometry")
    ap.add_argument("--crs", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--value", required=True)
    ap.add_argument("--value-label", required=True)
    ap.add_argument("--unit", required=True)
    ap.add_argument("--bins", type=float, nargs="+", required=True)
    ap.add_argument("--palette")
    ap.add_argument("--theme", choices=sorted(THEMES), default="light")
    ap.add_argument("--width-range", type=float, nargs=2, default=(0.5, 3.5))
    ap.add_argument("--base-width", type=float, default=0.25)
    ap.add_argument("--highlight")
    ap.add_argument("--highlight-label", default="強調した辺")
    ap.add_argument("--label-col")
    ap.add_argument("--points", action="append", default=[])
    ap.add_argument("--view", type=float, nargs=4)
    ap.add_argument("--title", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--font")
    ap.add_argument("--png", required=True)
    a = ap.parse_args(argv)

    bins = list(a.bins)
    if any(b <= 0 for b in bins) or any(x >= y for x, y in zip(bins, bins[1:])):
        raise SystemExit("--bins must be positive and increasing (upper edges of the classes)")
    theme = THEMES[a.theme]
    palette = a.palette or DEFAULT_PALETTE[a.theme]
    if palette.lower().rstrip("_r") in RAINBOW:
        raise SystemExit(f"{palette} is a rainbow palette: its lightness does not follow the values")
    if not palette_contrast_ok(palette, a.theme):
        raise SystemExit(f"{palette}: on the {a.theme} background its high end contrasts less than its low end; "
                         f"the busiest edges would fade. Use a palette whose high end stands out "
                         f"(default {DEFAULT_PALETTE[a.theme]})")

    df, geoms = read_edges(a.edges, a.geometry, [a.value, a.highlight, a.label_col])
    n = len(df)
    cls = classify(df[a.value].astype(float).values, bins)
    k = len(bins)
    counts = {"zero": int((cls == -1).sum()), "nodata": int((cls == -2).sum()),
              "classes": [int((cls == i).sum()) for i in range(k)]}
    assert counts["zero"] + counts["nodata"] + sum(counts["classes"]) == n
    hl = df[a.highlight].fillna(False).astype(bool).values if a.highlight else np.zeros(n, bool)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    from cjk_font import use_cjk_font

    labels = []
    if a.label_col:
        labels = [str(x) for x in df.loc[hl, a.label_col].dropna().unique() if str(x)]
    lo = [0.0] + bins[:-1]
    cls_names = [f"{_fmt(l)} より大きく {_fmt(h)} 以下" for l, h in zip(lo, bins)]
    point_specs = [p.split(",") for p in a.points]
    text = " ".join([a.title, a.note, a.value_label, a.unit, a.highlight_label, a.source, "0 値なし 1 km m",
                     *cls_names, *labels, *[s[1] for s in point_specs]])
    font = use_cjk_font(text, a.font)

    segs = segments(geoms)
    colours = palette_colours(palette, k)
    widths = class_widths(k, a.width_range)
    fig, ax = plt.subplots(figsize=(10, 10))
    fig.patch.set_facecolor(theme["bg"])
    ax.set_facecolor(theme["bg"])

    def draw(mask, **kw):
        s = [p for i in np.flatnonzero(mask) for p in segs[i]]
        if s:
            ax.add_collection(LineCollection(s, **kw))

    draw(cls == -1, colors=theme["base"], linewidths=a.base_width, zorder=1)
    draw(cls == -2, colors=theme["nodata"], linewidths=a.base_width, linestyles=":", zorder=1)
    draw(hl, colors=theme["outline"], linewidths=max(widths) + 3, zorder=2, capstyle="round")
    for i in range(k):  # low classes first, so the busiest edges lie on top
        draw(cls == i, colors=[colours[i]], linewidths=widths[i], zorder=3 + i, capstyle="round")

    points_meta, marks, point_handles = [], [], []
    for spec in point_specs:
        path, label, marker, colour = spec
        xy = read_points(path)
        m = ax.scatter(xy[:, 0], xy[:, 1], marker=marker, s=36, facecolor=colour, edgecolor=theme["bg"], lw=0.7,
                       zorder=10 + k, label=label)
        point_handles.append(m)
        marks.append((label, xy))
        points_meta.append({"label": label, "path": path, "n": int(len(xy))})

    x0, y0, x1, y1 = a.view if a.view else _bounds(geoms)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(aspect(a.crs, y0, y1))

    # labels are placed after the view is fixed, so that their drawn boxes can be tested against the points
    # and the labels already placed; the first offset that overlaps nothing is kept
    from context_map import text_overlaps
    texts = []
    for lab in labels:
        sel = hl & (df[a.label_col].astype(str).values == lab)
        g = geoms[np.flatnonzero(sel)[0]]
        p = g.interpolate(0.5, normalized=True)
        for off in LABEL_OFFSETS:
            t = ax.annotate(lab, (p.x, p.y), xytext=off, textcoords="offset points", fontsize=8,
                            color=theme["text"], zorder=20 + k, ha="left" if off[0] >= 0 else "right",
                            va="bottom" if off[1] >= 0 else "top",
                            bbox=dict(boxstyle="round,pad=0.15", fc=theme["bg"], ec="none", alpha=0.75))
            if not point_overlaps(fig, ax, [t], marks) and not text_overlaps(fig, texts + [t]):
                break
            if off != LABEL_OFFSETS[-1]:
                t.remove()
        texts.append(t)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    handles = [Line2D([], [], color=colours[i], lw=widths[i], label=f"{cls_names[i]} ({counts['classes'][i]})")
               for i in range(k)][::-1]
    handles.append(Line2D([], [], color=theme["base"], lw=a.base_width * 3, label=f"0 ({counts['zero']})"))
    if counts["nodata"]:
        handles.append(Line2D([], [], color=theme["nodata"], lw=1, ls=":", label=f"値なし ({counts['nodata']})"))
    if hl.any():
        handles.append(Line2D([], [], color=theme["outline"], lw=3, label=a.highlight_label))
    handles += point_handles
    leg = ax.legend(handles=handles, title=f"{a.value_label} ({a.unit})", loc="upper left", bbox_to_anchor=(1.01, 1),
                    frameon=False, labelcolor=theme["text"], fontsize=8, title_fontsize=9)
    leg.get_title().set_color(theme["text"])
    if a.title:
        ax.set_title(a.title, color=theme["text"], fontsize=11)
    foot = f"{a.crs}。{a.source}" + (f"。{a.note}" if a.note else "")
    ax.text(0, -0.01, foot, transform=ax.transAxes, va="top", fontsize=7, color=theme["text"])
    if a.crs.upper() not in GEOGRAPHIC:
        _scale_bar(ax, x0, x1, y0, y1, theme["text"])

    overlaps = text_overlaps(fig, texts, legends=[leg]) + point_overlaps(fig, ax, texts, marks)
    png = Path(a.png)
    fig.savefig(png, dpi=150, bbox_inches="tight", facecolor=theme["bg"])
    plt.close(fig)

    meta = dict(question=a.question, source=a.source, edges_file=str(a.edges), crs=a.crs, value=a.value,
                value_label=a.value_label, unit=a.unit, bins=bins, class_labels=cls_names, counts=counts, edges=n,
                palette=palette, theme=a.theme, widths=[round(w, 3) for w in widths],
                highlighted=int(hl.sum()), labels=labels, points=points_meta, view=[x0, y0, x1, y1],
                text_overlaps=[list(p) for p in overlaps], font=font)
    png.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k_: meta[k_] for k_ in ("counts", "edges", "highlighted", "text_overlaps")}, ensure_ascii=False))


def _fmt(x):
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,}"


def _bounds(geoms):
    import shapely
    b = shapely.total_bounds(geoms)
    return float(b[0]), float(b[1]), float(b[2]), float(b[3])


def _scale_bar(ax, x0, x1, y0, y1, colour):
    span = (x1 - x0) / 5
    length = 10 ** math.floor(math.log10(span))
    for m in (5, 2, 1):
        if m * length <= span:
            length *= m
            break
    xs = x1 - (x1 - x0) * 0.04 - length
    ys = y0 + (y1 - y0) * 0.04
    ax.plot([xs, xs + length], [ys, ys], color=colour, lw=2, zorder=50)
    lab = f"{length / 1000:g} km" if length >= 1000 else f"{length:g} m"
    ax.text(xs + length / 2, ys + (y1 - y0) * 0.01, lab, ha="center", va="bottom", fontsize=8, color=colour, zorder=50)


if __name__ == "__main__":
    main()
