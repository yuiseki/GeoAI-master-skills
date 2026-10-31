"""What a map needs besides its values, so that a reader can tell where things are and how far to trust them.

Functions used by classify_map.py, and a command that turns grid-cell centres into squares:

    uvx --with numpy --with duckdb --with shapely python context_map.py squares cells.csv \\
        --row cell_row --col cell_col --x lon --y lat --out cells.parquet

- aspect: a map in longitude and latitude is stretched by 1 / cos(latitude); drawn 1:1 it is squashed
  (at 43 degrees north, east-west distances look 37% too long).
- fit_grid: the squares of a regular grid, rebuilt from the cell centres and the row and column numbers.
  A centre off the grid, or cells not square in the map's units, stops the run instead of drawing gaps.
  With a single row (or column) squareness cannot be checked, and the result says so. The step is the
  median slope over at most MAX_PAIRS pairs of centres (all pairs when there are few, a seeded sample
  otherwise), so memory and time grow with the number of cells, not with its square.
- squares: the command runs under an address-space limit (--max-memory-gb, default 4): a run that would
  need more stops with MemoryError instead of taking the machine's memory.
- check_context_crs: a background layer in another CRS stops the run, unless the difference is declared
  (it is recorded with the map).
- label_areas: names of the background areas, only for areas big enough in the view, on a white box.
- areas_containing: every background area holding a point. Administrative polygons often overlap
  along shared borders, so a point on a border belongs to both.
- text_overlaps: pairs of texts that overlap one another or a legend, measured on the drawn figure.
  A label under a legend, or a rank number hidden by its neighbour, is found without looking.
"""

import argparse
import math
try:
    import resource
except ImportError:
    resource = None

import numpy as np

GEOGRAPHIC = {"EPSG:4326", "OGC:CRS84", "CRS84", "EPSG:4612", "EPSG:6668", "EPSG:4019", "EPSG:4269", "EPSG:4258"}
LAND = "#efece6"   # background areas, under the values
WATER = "#dbe9f2"  # what is not in any background area
LINE = "#4d4d4d"   # background boundaries, over the values
MAX_PAIRS = 200_000  # pairs of centres used for the median slope; all pairs below this


def aspect(crs, ymin, ymax):
    """The y / x display ratio: 1 / cos(mid latitude) for longitude and latitude, 1 otherwise."""
    if crs.upper() in GEOGRAPHIC:
        return 1 / math.cos(math.radians((ymin + ymax) / 2))
    return 1.0


def fit_grid(rows, cols, x, y, tol=1e-3):
    """Squares of a regular grid from the centres; rows run in y, columns in x (either direction)."""
    import shapely

    rows, cols = np.asarray(rows, float), np.asarray(cols, float)
    x, y = np.asarray(x, float), np.asarray(y, float)

    def slope(i, v):
        # median of the pairwise slopes (Theil-Sen): one misplaced centre cannot move it. All pairs of n
        # centres are n (n - 1) / 2 (2.2 billion for 66,460 cells), so above MAX_PAIRS a seeded sample is used.
        n = len(i)
        if n * (n - 1) // 2 <= MAX_PAIRS:
            a, b = np.triu_indices(n, 1)
        else:
            rng = np.random.default_rng(0)
            a, b = rng.integers(0, n, 2 * MAX_PAIRS), rng.integers(0, n, 2 * MAX_PAIRS)
        keep = i[a] != i[b]
        a, b = a[keep][:MAX_PAIRS], b[keep][:MAX_PAIRS]
        return float(np.median((v[a] - v[b]) / (i[a] - i[b]))) if len(a) else None

    sx, sy = slope(cols, x), slope(rows, y)
    if sx is None and sy is None:
        raise ValueError("one cell gives no grid; at least two rows or two columns are needed")
    square_checked = sx is not None and sy is not None
    if square_checked and not math.isclose(abs(sx), abs(sy), rel_tol=tol):
        raise ValueError(f"cells are not square in the map's units: {abs(sx):g} by {abs(sy):g}")
    sx = sx if sx is not None else abs(sy)
    sy = sy if sy is not None else -abs(sx)
    step = abs(sx)
    x0, y0 = float(np.median(x - cols * sx)), float(np.median(y - rows * sy))
    off = max(np.abs(x - (x0 + cols * sx)).max(), np.abs(y - (y0 + rows * sy)).max())
    if off > step * tol:
        raise ValueError(f"a centre is off the grid by {off:g} (cell size {step:g})")
    h = step / 2
    squares = [shapely.box(a - h, b - h, a + h, b + h) for a, b in zip(x0 + cols * sx, y0 + rows * sy)]
    return {"step": step, "squares": squares, "square_checked": square_checked}


def check_context_crs(crs, context_crs, accepted):
    """None when the CRS agree; the declared reason when they differ and one is given; else stop."""
    if crs.upper() == context_crs.upper():
        return None
    if not accepted:
        raise SystemExit(f"the background is in {context_crs} and the values in {crs}: transform one, or say why the "
                         "difference is below what the map shows (--accept-crs-difference)")
    return accepted


def read_areas(path, name_col, where=None, view=None, geometry="geometry"):
    """(name, geometry) of a background layer, clipped to view (a shapely geometry) when given."""
    import duckdb
    import shapely

    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs")
    src = f"read_parquet('{path}')" if str(path).endswith(".parquet") else f"ST_Read('{path}')"
    cond = f"where {where}" if where else ""
    rows = con.sql(f'select "{name_col}", ST_AsWKB("{geometry}") from {src} {cond}').fetchall()
    out = []
    for name, wkb in rows:
        if wkb is None:
            continue
        g = shapely.from_wkb(bytes(wkb))
        if view is not None:
            if not g.intersects(view):
                continue
            g = g.intersection(view)
        out.append(("" if name is None else str(name), g))
    return out


def _patches(ax, geom, **kw):
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath

    for poly in getattr(geom, "geoms", [geom]):
        if poly.geom_type != "Polygon" or poly.is_empty:
            continue
        verts, codes = [], []
        for ring in [poly.exterior, *poly.interiors]:
            xy = list(ring.coords)
            verts += xy
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(xy) - 2) + [MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes), **kw))


def draw_areas_under(ax, areas):
    ax.set_facecolor(WATER)
    for _, g in areas:
        _patches(ax, g, facecolor=LAND, edgecolor="none", zorder=0)


def draw_areas_over(ax, areas):
    for _, g in areas:
        _patches(ax, g, facecolor="none", edgecolor=LINE, linewidth=0.6, zorder=4)


def label_areas(ax, areas, view, min_share=0.005, fontsize=8):
    """Name the areas whose part in the view (xmin, xmax, ymin, ymax) is at least min_share of it."""
    xmin, xmax, ymin, ymax = view
    whole = (xmax - xmin) * (ymax - ymin)
    texts = []
    for name, g in areas:
        if not name or g.is_empty or g.area < min_share * whole:
            continue
        part = max(getattr(g, "geoms", [g]), key=lambda p: p.area)
        p = part.representative_point()
        if xmin <= p.x <= xmax and ymin <= p.y <= ymax:
            texts.append(ax.text(p.x, p.y, name, fontsize=fontsize, ha="center", va="center", color="#222222",
                                 zorder=6, bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none",
                                                 "alpha": 0.75}))
    return texts


def areas_containing(point, areas):
    return "/".join(name for name, g in areas if g.covers(point))


def text_overlaps(fig, texts, legends=()):
    """(text, text) and (text, "legend") pairs whose drawn boxes overlap."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    boxes = [(t.get_text(), t.get_window_extent(r)) for t in texts if t.get_visible() and t.get_text()]
    found = []
    for i, (a, ba) in enumerate(boxes):
        for b, bb in boxes[i + 1:]:
            if ba.overlaps(bb):
                found.append((a, b))
        for leg in legends:
            if ba.overlaps(leg.get_window_extent(r)):
                found.append((a, "legend"))
    return found


def limit_memory(gb):
    """Cap this process's address space, so that an input too big for the method stops it with MemoryError."""
    if gb and gb > 0:
        cap = int(gb * 1024 ** 3)
        if resource is not None:
            soft, hard = resource.getrlimit(resource.RLIMIT_DATA)
            resource.setrlimit(resource.RLIMIT_DATA, (cap if hard == resource.RLIM_INFINITY else min(cap, hard), hard))


def squares_command(a):
    import csv

    limit_memory(a.max_memory_gb)

    import duckdb

    with open(a.table, newline="") as fh:
        rows = list(csv.DictReader(fh))
    grid = fit_grid([float(r[a.row]) for r in rows], [float(r[a.col]) for r in rows],
                    [float(r[a.x]) for r in rows], [float(r[a.y]) for r in rows])
    con = duckdb.connect()
    con.sql("install spatial; load spatial")
    con.sql("set preserve_insertion_order = true")
    con.sql(f"create table t as select * from read_csv('{a.table}')")
    con.sql("create table w (n bigint, wkt varchar)")
    con.executemany("insert into w values (?, ?)", [(i, s.wkt) for i, s in enumerate(grid["squares"])])
    # rowid follows the file's row order, the same order as the squares
    con.sql(f"copy (select t.*, ST_GeomFromText(w.wkt) as geometry from t join w on t.rowid = w.n order by w.n) "
            f"to '{a.out}' (format parquet)")
    print(f"{len(rows)} squares of {grid['step']:g} (map units) written to {a.out}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("squares", help="grid-cell centres (CSV) to square polygons (GeoParquet)")
    s.add_argument("table")
    for k in ("row", "col", "x", "y", "out"):
        s.add_argument(f"--{k}", required=True)
    s.add_argument("--max-memory-gb", type=float, default=4.0,
                   help="address-space limit of this process in GB (0 for none); a run that needs more stops")
    a = p.parse_args()
    squares_command(a)


if __name__ == "__main__":
    main()
