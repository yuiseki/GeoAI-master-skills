"""The rules of the plan for one underpass: which road passes under it, its longitudinal profile, and the depth of
the dip. Kept apart from the I/O so that the rules can be tested.

Coordinates are EPSG:3857 (as the OSM table). Ground metres are 3857 units times cos(lat), taken at the point; this is
exact enough within a few hundred metres.
"""
import math

import numpy as np
from shapely.geometry import LineString, Point

ROAD_CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                "living_street", "service", "motorway_link", "trunk_link", "primary_link", "secondary_link",
                "tertiary_link"}
STEP = 2.5        # m between samples of the profile
BOTTOM_WITHIN = 30.0   # m from the point where the bottom is looked for
MAX_NAN = 0.10    # share of samples without a value above which the profile is not measurable
CHAIN_ANGLE = 45.0     # degrees; a line continues the chain if it turns by no more than this
AMBIG_EXTRA = 10.0     # m; another line this much farther than the nearest can make the match ambiguous
AMBIG_ANGLE = 30.0     # degrees between the two lines' directions


def layer_value(v):
    """First number of an OSM layer value ('0;1' -> 0.0); None if there is none."""
    if v is None:
        return None
    try:
        return float(str(v).split(";")[0])
    except ValueError:
        return None


def eligible(highway, bridge, layer):
    """A line that can be the road under the underpass: a road class, not a bridge, not above ground level."""
    if highway not in ROAD_CLASSES:
        return False
    if bridge is not None and bridge != "no":
        return False
    lv = layer_value(layer)
    return lv is None or lv <= 0


def direction(line, d):
    """Unit direction of a line at distance d along it (3857 units)."""
    a = line.interpolate(max(d - 1.0, 0.0))
    b = line.interpolate(min(d + 1.0, line.length))
    v = np.array([b.x - a.x, b.y - a.y])
    n = np.hypot(*v)
    return v / n if n else v


def angle_between(u, v, undirected=True):
    c = float(np.clip(np.dot(u, v), -1, 1))
    a = math.degrees(math.acos(c))
    return min(a, 180 - a) if undirected else a


def ambiguous(point, lines, nearest, scale):
    """True if another line within the nearest distance + AMBIG_EXTRA runs in a direction more than AMBIG_ANGLE apart."""
    d0 = lines[nearest].distance(point)
    u = direction(lines[nearest], lines[nearest].project(point))
    for i, ln in enumerate(lines):
        if i == nearest:
            continue
        if ln.distance(point) * scale <= d0 * scale + AMBIG_EXTRA:
            if angle_between(u, direction(ln, ln.project(point))) > AMBIG_ANGLE:
                return True
    return False


def _out_dir(coords):
    v = np.array(coords[-1]) - np.array(coords[-2])
    return v / (np.hypot(*v) or 1)


def node_index(lines, all_vertices):
    """Map a node to (line index, vertex position) pairs: the lines' end nodes only (the plan's rule), or every
    vertex (a line that passes through the node can continue the chain too)."""
    nodes = {}
    for i, ln in enumerate(lines):
        c = list(ln.coords)
        # a closed way (first node = last node) is entered at its first node only, as the plan's run did
        ends = [0] if c[0] == c[-1] else [0, len(c) - 1]
        for j in (range(len(c)) if all_vertices else ends):
            nodes.setdefault(tuple(c[j]), []).append((i, j))
    return nodes


def extend_chain(start, nodes, lines, reach):
    """Extend `start` (a list of coordinates) at its last node with the lines through that node (`nodes`, from
    node_index) that turn by no more than CHAIN_ANGLE, until the added length reaches `reach` (3857 units). A line
    through the node can be followed either way from it. Returns the coordinates and the line indices used."""
    coords, used, added = list(start), [], 0.0
    while added < reach:
        node = tuple(coords[-1])
        best, best_a, best_c = None, CHAIN_ANGLE, None
        din = _out_dir(coords)
        for i, j in nodes.get(node, ()):
            if i in used:
                continue
            full = list(lines[i].coords)
            for c in (full[j:], full[j::-1]):
                if len(c) < 2:
                    continue
                dout = np.array(c[1]) - np.array(c[0])
                dout = dout / (np.hypot(*dout) or 1)
                a = angle_between(din, dout, undirected=False)
                if a <= best_a:
                    best, best_a, best_c = i, a, c
        if best is None:
            break
        used.append(best)
        coords.extend(best_c[1:])
        added += LineString(best_c).length
    return coords, used


def build_chain(k, lines, nodes, reach):
    """The road through line k, extended at both ends by `reach` (3857 units)."""
    base = list(lines[k].coords)
    fwd, used_f = extend_chain(base, nodes, lines, reach)
    back, used_b = extend_chain(fwd[::-1], nodes, lines, reach + LineString(fwd).length - LineString(base).length)
    return LineString(back[::-1]), [k] + used_f + used_b


def depth(s, e, L, bottom_within=BOTTOM_WITHIN):
    """Depth of the dip on a profile: s (m, 0 at the point) and elevations e. Returns (depth, bottom_s, measurable)
    for the half-length L. The bottom is looked for within `bottom_within` m of the point (the plan's 30 m; L for
    the whole profile). Not measurable if more than MAX_NAN of the samples within L have no value or the profile
    reaches less than L / 2 on either side."""
    s, e = np.asarray(s, float), np.asarray(e, float)
    w = np.abs(s) <= L + 1e-9
    s, e = s[w], e[w]
    if len(s) == 0 or s.min() > -L / 2 or s.max() < L / 2 or np.isnan(e).mean() > MAX_NAN:
        return None, None, False
    near = np.abs(s) <= bottom_within
    if np.all(np.isnan(e[near])):
        return None, None, False
    ib = np.flatnonzero(near)[np.nanargmin(e[near])]
    left, right = e[:ib + 1], e[ib:]
    sill = min(np.nanmax(left), np.nanmax(right))
    return float(sill - e[ib]), float(s[ib]), True


def surface_depth(win, m, r, c):
    """The plan's simplest solver: median of the pixels within 50 m minus the lowest within 10 m (positive = dip)."""
    yy, xx = np.indices(win.shape)
    d = np.hypot(yy - r, xx - c) * m
    a50, a10 = win[d <= 50], win[d <= 10]
    if np.all(np.isnan(a10)) or np.isnan(a50).mean() > MAX_NAN:
        return None
    return float(np.nanmedian(a50) - np.nanmin(a10))


def merc_to_lonlat(x, y):
    lon = x / 6378137 * 180 / math.pi
    lat = math.degrees(2 * math.atan(math.exp(y / 6378137)) - math.pi / 2)
    return lon, lat


def lonlat_to_merc(lon, lat):
    return 6378137 * math.radians(lon), 6378137 * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def samples(chain, point, scale, L):
    """Positions along the chain every STEP m within L of the projected point: (s in m, x, y in 3857)."""
    s0 = chain.project(point)
    out = []
    n = int(L / STEP)
    for i in range(-n, n + 1):
        d = s0 + i * STEP / scale
        if 0 <= d <= chain.length:
            p = chain.interpolate(d)
            out.append((i * STEP, p.x, p.y))
    return out, s0 * scale, (chain.length - s0) * scale


__all__ = ["ROAD_CLASSES", "eligible", "layer_value", "ambiguous", "build_chain", "depth", "surface_depth",
           "merc_to_lonlat", "lonlat_to_merc", "samples", "node_index", "Point", "LineString"]
