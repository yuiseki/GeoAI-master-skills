"""Functions of stage B (see EXPERIMENT_PLAN_B.md): the GSI depth from map tiles, our own GRD processing, and the
water surface and depth of article 2.
"""
import math

import numpy as np
from scipy import ndimage

FOUR = ndimage.generate_binary_structure(2, 1)


# --- the GSI depth -------------------------------------------------------------------------------------------------

def legend_table(rgb, alpha, top_m=0.0, bottom_m=10.0):
    """The colour ramp of a vertical legend bar: the median colour of each row of the opaque box, top to bottom.

    rgb (h, w, 3) and alpha (h, w) are the legend image and its mask. The mask also covers a black drop shadow around
    the bar, so the bar is where the mask is opaque and the colour is not black. Returns depths (n,) and colours (n, 3).
    """
    bar = (alpha > 128) & (rgb.astype(int).sum(axis=-1) > 30)
    rows = np.where(bar.any(axis=1))[0]
    cols = np.where(bar.any(axis=0))[0]
    if len(rows) < 10 or len(cols) < 3:
        raise ValueError("no legend bar in the mask")
    r0, r1, c0, c1 = rows[0], rows[-1], cols[0], cols[-1]
    margin = max((c1 - c0) // 4, 1)
    box = rgb[r0:r1 + 1, c0 + margin:c1 + 1 - margin].astype(float)
    colours = np.median(box, axis=1)
    return np.linspace(top_m, bottom_m, len(colours)), colours


def colour_to_depth(rgba, depths, colours, max_dist=10.0):
    """Depth of each opaque pixel from the nearest legend colour; nan where transparent or farther than max_dist.

    Returns (depth, n_far): n_far counts opaque pixels left out for being far from every legend colour.
    """
    flat = rgba.reshape(-1, rgba.shape[-1]).astype(float)
    opaque = flat[:, 3] > 0 if flat.shape[1] == 4 else np.ones(len(flat), bool)
    out = np.full(len(flat), np.nan)
    if opaque.any():
        c = flat[opaque, :3]
        uniq, inv = np.unique(c, axis=0, return_inverse=True)
        d = np.sqrt(((uniq[:, None, :] - colours[None, :, :]) ** 2).sum(-1))
        best, dist = d.argmin(1), d.min(1)
        val = np.where(dist <= max_dist, depths[best], np.nan)
        out[opaque] = val[inv.ravel()]
        n_far = int((dist[inv.ravel()] > max_dist).sum())
    else:
        n_far = 0
    return out.reshape(rgba.shape[:2]), n_far


def tile_pixel_lonlat(x0, y0, z, shape, size=256):
    """Longitude and latitude of the centres of a mosaic of tiles whose top left tile is (x0, y0)."""
    rows, cols = np.mgrid[0:shape[0], 0:shape[1]]
    n = size * 2 ** z
    gx = x0 * size + cols + 0.5
    gy = y0 * size + rows + 0.5
    lon = gx / n * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * gy / n))))
    return lon, lat


def to_grid_mean(values, x, y, transform, shape, min_cover=0.5):
    """Mean of values (nan = no value) of the points (x, y) falling in each grid cell; nan where fewer than min_cover
    of the points in the cell have a value, or no point falls in it. transform is (a, b, c, d, e, f) of an
    axis-aligned grid."""
    a, _, c, _, e, f = transform[:6]
    col = np.floor((x - c) / a).astype(int)
    row = np.floor((y - f) / e).astype(int)
    inside = (row >= 0) & (row < shape[0]) & (col >= 0) & (col < shape[1])
    idx = row[inside] * shape[1] + col[inside]
    v = values[inside]
    has = ~np.isnan(v)
    n_all = np.bincount(idx, minlength=shape[0] * shape[1])
    n_val = np.bincount(idx[has], minlength=shape[0] * shape[1])
    s = np.bincount(idx[has], weights=v[has], minlength=shape[0] * shape[1])
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = s / n_val
        ok = (n_all > 0) & (n_val >= min_cover * n_all) & (n_val > 0)
    return np.where(ok, mean, np.nan).reshape(shape)


# --- GRD processing ------------------------------------------------------------------------------------------------

def vectors_to_grid(lines, pixels, values, rows, cols):
    """Interpolate LUT vectors (one per line, each with its own pixels and values) to the grid rows x cols:
    linearly along each vector's pixels, then linearly across lines. Outside the given lines or pixels the end
    values are held."""
    per_line = np.array([np.interp(cols, p, v) for p, v in zip(pixels, values)])
    out = np.empty((len(rows), len(cols)))
    for j in range(len(cols)):
        out[:, j] = np.interp(rows, lines, per_line[:, j])
    return out


def azimuth_noise(blocks, rows, cols):
    """Azimuth noise scaling on the grid from blocks of (first_line, last_line, first_sample, last_sample, lines,
    lut). Pixels in no block get 1."""
    out = np.ones((len(rows), len(cols)))
    for fl, ll, fs, ls, lines, lut in blocks:
        rmask = (rows >= fl) & (rows <= ll)
        cmask = (cols >= fs) & (cols <= ls)
        if rmask.any() and cmask.any():
            out[np.ix_(rmask, cmask)] = np.interp(rows[rmask], lines, lut)[:, None]
    return out


def sigma0(dn, sigma_lut, noise, floor=1e-5):
    """Calibrated, noise-removed backscatter (DN^2 - noise) / A^2, with values below floor set to floor."""
    s = (dn.astype(float) ** 2 - noise) / sigma_lut ** 2
    return np.maximum(s, floor)


class Geolocation:
    """Map (lon, lat, ellipsoidal height) to (line, pixel) of a GRD from its geolocation grid.

    Each grid point's pixel is moved to the pixel it would have at height 0 (pixel + h / (tan(inc) * spacing)).
    Line, pixel at height 0 and the incidence angle are then interpolated linearly in lon, lat over a Delaunay
    triangulation of the grid points (exact at the points). A point at height H is at pixel0 - H / (tan(inc) * spacing):
    a higher point is nearer in range. Ascending, right looking: pixel grows away from the track.
    """

    def __init__(self, line, pixel, lon, lat, height, incidence, spacing):
        from scipy.interpolate import LinearNDInterpolator
        self.spacing = spacing
        t = np.tan(np.radians(incidence))
        p0 = np.asarray(pixel, float) + np.asarray(height, float) / (t * spacing)
        xy = np.column_stack([lon, lat])
        self.f = LinearNDInterpolator(xy, np.column_stack([line, p0, incidence]))

    def __call__(self, lon, lat, height):
        v = self.f(np.ravel(lon), np.ravel(lat))
        line, p0, inc = v[:, 0], v[:, 1], v[:, 2]
        pix = p0 - np.ravel(height) / (np.tan(np.radians(inc)) * self.spacing)
        shape = np.shape(lon)
        return line.reshape(shape), pix.reshape(shape), inc.reshape(shape)


def sample_bilinear(img, rows, cols):
    """Bilinear sample of img at fractional (rows, cols) (pixel centres at integers); nan outside."""
    return ndimage.map_coordinates(img.astype(float), [rows, cols], order=1, mode="constant", cval=np.nan)


def shift_by_correlation(a, b, max_shift=5):
    """The (row, col) shift s with a[i] ~ b[i + s], by normalised cross-correlation over the pixels valid in both,
    refined to sub-pixel by a parabola through the scores next to the best integer shift. Returns (dr, dc, score)."""
    h, w = a.shape
    scores = {}
    for dr in range(-max_shift, max_shift + 1):
        for dc in range(-max_shift, max_shift + 1):
            aa = a[max(0, -dr):h - max(0, dr), max(0, -dc):w - max(0, dc)]
            bb = b[max(0, dr):h - max(0, -dr), max(0, dc):w - max(0, -dc)]
            ok = ~(np.isnan(aa) | np.isnan(bb))
            x, y = aa[ok] - aa[ok].mean(), bb[ok] - bb[ok].mean()
            scores[(dr, dc)] = float((x * y).sum() / np.sqrt((x * x).sum() * (y * y).sum()))
    best = max(scores, key=scores.get)

    def refine(axis):
        lo = list(best)
        hi = list(best)
        lo[axis] -= 1
        hi[axis] += 1
        m0, m1, m2 = scores.get(tuple(lo)), scores[best], scores.get(tuple(hi))
        if m0 is None or m2 is None or m0 - 2 * m1 + m2 == 0:
            return 0.0
        return 0.5 * (m0 - m2) / (m0 - 2 * m1 + m2)
    return best[0] + refine(0), best[1] + refine(1), scores[best]


# --- surfaces and depth (article 2) --------------------------------------------------------------------------------

def surface_quantile(part, dem, q=0.99):
    """The q quantile of the ground in part, leaving out nan; nan when the part has no ground value."""
    g = dem[part]
    return float(np.nanquantile(g, q)) if (~np.isnan(g)).any() else np.nan


def surface_iou(part, water, dem, pad=10, step=0.01):
    """The height s that maximises IoU({water}, {dem < s}) in the bounding box of part widened by pad pixels.
    Candidates run from the 1 % to the 99 % point of dem in part, step apart. Returns (s, iou)."""
    rows, cols = np.where(part)
    r0, r1 = max(rows.min() - pad, 0), rows.max() + pad + 1
    c0, c1 = max(cols.min() - pad, 0), cols.max() + pad + 1
    w, d = water[r0:r1, c0:c1], dem[r0:r1, c0:c1]
    g = dem[part]
    if np.isnan(g).all():
        return np.nan, np.nan
    lo, hi = np.nanquantile(g, [0.01, 0.99])
    best = (np.nan, -1.0)
    for s in np.arange(lo, hi + step / 2, step):
        below = d < s
        union = (w | below).sum()
        iou = (w & below).sum() / union if union else 0.0
        if iou > best[1]:
            best = (float(s), float(iou))
    return best


def parts(mask, min_size=100):
    lab, n = ndimage.label(mask, structure=FOUR)
    if n == 0:
        return lab
    size = np.bincount(lab.ravel())
    keep = size >= min_size
    keep[0] = False
    new = np.zeros(n + 1, int)
    new[keep] = np.arange(1, keep.sum() + 1)
    return new[lab]


def depth_from_surfaces(labels, surfaces, dem):
    """Depth (surface - ground, at least 0) inside each part; nan outside the parts."""
    out = np.full(dem.shape, np.nan)
    for k, s in surfaces.items():
        m = labels == k
        out[m] = np.maximum(s - dem[m], 0)
    return out


def extrapolate(t1, s1, t2, s2, t):
    """The surface at time t on the line through (t1, s1) and (t2, s2); times in any common unit."""
    return s2 + (s2 - s1) * (t - t2) / (t2 - t1)
