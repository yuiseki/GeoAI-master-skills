"""Map panels that line up: fix the map's size first, add the decorations around it, and check it in pixels.

Maps meant to be compared side by side must show the same extent at the same scale. When each panel is saved
with bbox_inches="tight" (or laid out by tight_layout), it is cropped to its own title, legend and colorbar,
so the map lands at a different place and size in each image, and resizing whole images to line them up also
scales the text. Here the map's height in inches and the extent decide the map's rectangle; the margins
(left, right, bottom, top, in inches) hold the decorations; a colorbar is either shown or only reserved
(the same blank room, so the maps of panels with and without one stay the same). save() writes the full canvas
without cropping and returns the layout in pixels; check_panels() compares those records; assemble() pastes
panels into one image without scaling, after checking that their maps coincide.

The approach follows CaMa-Flood's figure guideline (map-area-first layout, virtual colorbars; Apache-2.0,
global-hydrodynamics/CaMa-Flood_v4, visualization/figure_making_guideline.md). No code was taken from it.

In a script:
    fig, ax, cax = panel_layout.map_frame(view, y_over_x, map_h_in=4, right=2.5, cbar="shown")
    ... draw on ax; fig.colorbar(mappable, cax=cax); legend at bbox_to_anchor=(panel_layout.right_anchor(fig), 1)
    layout = panel_layout.save(fig, "a.png", [legend, title])     # stops if a decoration leaves the canvas

From the shell (the records are the "layout" key of each PNG's JSON, or the JSON itself):
    python panel_layout.py check a.json b.json
    python panel_layout.py assemble --cols 2 [--gap 20] --out ab.png a.png b.png
"""

import argparse
import math
import json
import sys
from pathlib import Path

CBAR_W, CBAR_PAD, CBAR_LABEL = 0.18, 0.12, 0.75     # inches: bar, gap to the map, room for ticks and label


def plan(view, y_over_x, map_h_in, left=0.3, right=0.3, bottom=0.5, top=0.5, cbar=None,
         cbar_w=CBAR_W, cbar_pad=CBAR_PAD, cbar_label=CBAR_LABEL):
    """Inches. view = (x0, y0, x1, y1) in data units; y_over_x the display ratio of a y unit to an x unit (1 for
    a projected CRS, 1 / cos(latitude) for longitude and latitude). cbar: None, "shown" or "reserved".
    Returns fig (w, h), map (left, bottom, w, h), cbar (left, bottom, w, h) or None, and the right margin's start."""
    x0, y0, x1, y1 = view
    if not (x1 > x0 and y1 > y0 and map_h_in > 0):
        raise SystemExit(f"empty view {view} or map height {map_h_in}")
    map_w = map_h_in * (x1 - x0) / ((y1 - y0) * y_over_x)
    m = (left, bottom, map_w, map_h_in)
    cb = None
    deco = left + map_w
    if cbar in ("shown", "reserved"):
        cb = (deco + cbar_pad, bottom, cbar_w, map_h_in)
        deco += cbar_pad + cbar_w + cbar_label
    elif cbar is not None:
        raise SystemExit(f"cbar must be None, 'shown' or 'reserved', not {cbar!r}")
    return {"fig": (deco + right, bottom + map_h_in + top), "map": m, "cbar": cb, "right_from": deco}


def map_frame(view, y_over_x, map_h_in, left=0.3, right=0.3, bottom=0.5, top=0.5, cbar=None, dpi=150, **kw):
    """A figure with the map axes at the planned place. cax is the colorbar axes (hidden when reserved) or None."""
    import matplotlib.pyplot as plt
    p = plan(view, y_over_x, map_h_in, left, right, bottom, top, cbar, **kw)
    # whole pixels: matplotlib truncates a fractional canvas (547.5 px is saved as 547), which would move the
    # map by a pixel between panels. The margins on the right and the top take the rounding up.
    W, H = (math.ceil(v * dpi - 1e-9) / dpi for v in p["fig"])
    p["fig"] = (W, H)
    fig = plt.figure(figsize=(W, H), dpi=dpi)
    frac = lambda r: (r[0] / W, r[1] / H, r[2] / W, r[3] / H)  # noqa: E731
    ax = fig.add_axes(frac(p["map"]))
    x0, y0, x1, y1 = view
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(y_over_x, adjustable="box")      # the box already has this ratio: nothing moves
    cax = None
    if p["cbar"]:
        cax = fig.add_axes(frac(p["cbar"]))
        if cbar == "reserved":
            cax.set_visible(False)
    fig._panel_layout = dict(p, view=list(view), cbar_mode=cbar, dpi=dpi, ax=ax, cax=cax)
    return fig, ax, cax


def right_anchor(fig):
    """Axes-fraction x where the right margin starts (beyond the colorbar room), for a legend's bbox_to_anchor."""
    p = fig._panel_layout
    left, _, w, _ = p["map"]
    return (p["right_from"] - left) / w + 0.02


def _px(fig, bbox):
    """A display bbox as integer pixels, origin at the top left."""
    H = fig.bbox.height
    return [round(bbox.x0), round(H - bbox.y1), round(bbox.x1), round(H - bbox.y0)]


def record(fig):
    p = fig._panel_layout
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    ax, cax = p["ax"], p["cax"]
    return {"canvas_px": [round(fig.bbox.width), round(fig.bbox.height)],
            "map_px": _px(fig, ax.get_window_extent(r)),
            "cbar_px": _px(fig, cax.get_position().transformed(fig.transFigure)) if cax is not None else None,
            "cbar": p["cbar_mode"], "view": p["view"], "dpi": p["dpi"]}


def overflow(fig, artists):
    """Artists whose drawn box leaves the canvas (by more than a pixel)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    out = []
    for a in artists:
        if a is None or not a.get_visible():
            continue
        b = a.get_window_extent(r)
        if b.x0 < -1 or b.y0 < -1 or b.x1 > fig.bbox.width + 1 or b.y1 > fig.bbox.height + 1:
            out.append(type(a).__name__ + (f" '{a.get_text()}'" if hasattr(a, "get_text") else ""))
    return out


def save(fig, path, decorations=(), **savefig_kw):
    """Write the whole canvas (no cropping) and return the layout record, checked against the planned map
    rectangle. Stops if one of the decorations (legend, title, footnote) leaves the canvas: widen the margin
    it lives in, wrap it, or shorten it; do not shrink the map."""
    p = fig._panel_layout
    bad = overflow(fig, decorations)
    if bad:
        raise SystemExit(f"outside the canvas: {bad}. Widen the margin that holds it (right=, top=, bottom=), "
                         "wrap it or shorten it; the map's size stays")
    for k in ("bbox_inches", "pad_inches"):
        if savefig_kw.pop(k, None) is not None:
            raise SystemExit(f"{k} would crop the panel to its own decorations; save() keeps the full canvas")
    rec = record(fig)
    want = [round(v * p["dpi"]) for v in p["map"]]
    got = rec["map_px"]
    if abs((got[2] - got[0]) - want[2]) > 1 or abs((got[3] - got[1]) - want[3]) > 1:
        raise SystemExit(f"the map is {got[2] - got[0]} x {got[3] - got[1]} px, planned {want[2]} x {want[3]}: "
                         "something resized the axes (set_aspect with another ratio, tight_layout)")
    fig.savefig(path, dpi=p["dpi"], **savefig_kw)
    from PIL import Image
    if list(Image.open(path).size) != rec["canvas_px"]:
        raise SystemExit(f"{path} is {Image.open(path).size}, planned {rec['canvas_px']}")
    return rec


def check_panels(records):
    """Differences that make panels not comparable: canvas, map rectangle, extent, colorbar room. And, for each
    shown colorbar, ends that do not meet the map's top and bottom."""
    probs = []
    first = records[0]
    for i, r in enumerate(records):
        for k in ("canvas_px", "map_px", "view", "dpi"):
            if r.get(k) != first.get(k):
                probs.append(f"panel {i}: {k} {r.get(k)} differs from panel 0 {first.get(k)}")
        if (r.get("cbar_px") is None) != (first.get("cbar_px") is None) or (
                r.get("cbar_px") and r["cbar_px"] != first["cbar_px"]):
            probs.append(f"panel {i}: cbar room {r.get('cbar_px')} differs from panel 0 {first.get('cbar_px')}; "
                         "reserve the same room (cbar='reserved') in panels without a colorbar")
        if r.get("cbar") == "shown" and r.get("cbar_px"):
            if [r["cbar_px"][1], r["cbar_px"][3]] != [r["map_px"][1], r["map_px"][3]]:
                probs.append(f"panel {i}: the colorbar {r['cbar_px']} does not run along the map {r['map_px']}")
    return probs


def assemble(pngs, records, out, cols, gap_px=0, background="white"):
    """Paste panels in rows of `cols`, without scaling. Their maps must coincide (check_panels)."""
    from PIL import Image
    probs = check_panels(records)
    if probs:
        raise SystemExit("panels do not line up: " + "; ".join(probs))
    w, h = records[0]["canvas_px"]
    n = len(pngs)
    rows = (n + cols - 1) // cols
    W, H = cols * w + (cols - 1) * gap_px, rows * h + (rows - 1) * gap_px
    big = Image.new("RGB", (W, H), background)
    panels = []
    for i, (png, r) in enumerate(zip(pngs, records)):
        im = Image.open(png).convert("RGB")
        if list(im.size) != r["canvas_px"]:
            raise SystemExit(f"{png} is {im.size}, its record says {r['canvas_px']}")
        dx, dy = (i % cols) * (w + gap_px), (i // cols) * (h + gap_px)
        big.paste(im, (dx, dy))
        m = r["map_px"]
        panels.append({"source": str(png), "map_px": [m[0] + dx, m[1] + dy, m[2] + dx, m[3] + dy]})
    big.save(out)
    rec = {"canvas_px": [W, H], "cols": cols, "gap_px": gap_px, "panels": panels, "view": records[0]["view"]}
    Path(out).with_suffix(".json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def _load(path):
    j = json.loads(Path(path).read_text(encoding="utf-8"))
    return j.get("layout", j)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("json", nargs="+")
    s = sub.add_parser("assemble")
    s.add_argument("png", nargs="+")
    s.add_argument("--cols", type=int, required=True)
    s.add_argument("--gap", type=int, default=0)
    s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        probs = check_panels([_load(p) for p in a.json])
        print("\n".join(probs) or f"{len(a.json)} panels line up")
        sys.exit(1 if probs else 0)
    recs = [_load(Path(p).with_suffix(".json")) for p in a.png]
    r = assemble(a.png, recs, a.out, a.cols, a.gap)
    print(json.dumps({"canvas_px": r["canvas_px"], "panels": len(r["panels"])}))


if __name__ == "__main__":
    main()
