"""Kernel density of points: the intensity (points per unit area) on a grid, with the bandwidth chosen by
likelihood cross-validation and the edge corrected.

    intensity       sum over points of a Gaussian kernel exp(-d^2 / 2h^2) / (2 pi h^2): points per square unit
                    of the distance (per km^2 on the sphere, per m^2 or km^2 on projected x, y)
    edge_mass       the share of each grid cell's kernel that falls inside the study window (a rectangle);
                    dividing by it (Diggle 1985) restores the intensity near the edge, where points beyond the
                    window were not observed
    lcv_bandwidth   the bandwidth maximising the leave-one-out log-likelihood of the points (likelihood
                    cross-validation); the score of every candidate is kept, to show how flat it is

The map depends on the bandwidth more than on anything else: a narrow one shows every small cluster, a wide one
merges them. Report the bandwidth, how it was chosen, and the map at a second bandwidth. An intensity map of
events that follow people is a map of people; divide by a baseline (population) to ask about risk, which this
script does not do.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with rasterio python kernel_density.py POINTS \\
        (--lon LON --lat LAT | --x X --y Y --crs EPSG) --window W S E N --cell C [--h H] [--out kde.tif]
        lon/lat: cell in degrees, h in km. x/y: cell and h in the CRS units.
"""

import argparse

import numpy as np
from scipy.stats import norm

EARTH_KM = 6371.0


def _d2(x, y, gx, gy, lonlat):
    if lonlat:
        lo, la = np.radians(x), np.radians(y)
        glo, gla = np.radians(gx), np.radians(gy)
        a = (np.sin((gla[:, None] - la[None]) / 2) ** 2
             + np.cos(gla[:, None]) * np.cos(la[None]) * np.sin((glo[:, None] - lo[None]) / 2) ** 2)
        return (2 * EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))) ** 2
    return (gx[:, None] - x[None]) ** 2 + (gy[:, None] - y[None]) ** 2


def intensity(x, y, gx, gy, h, lonlat=False, chunk=2000):
    x, y, gx, gy = (np.asarray(v, float) for v in (x, y, gx, gy))
    out = np.empty(len(gx))
    for s in range(0, len(gx), chunk):
        d2 = _d2(x, y, gx[s:s + chunk], gy[s:s + chunk], lonlat)
        out[s:s + chunk] = np.exp(-d2 / (2 * h * h)).sum(1) / (2 * np.pi * h * h)
    return out


def edge_mass(gx, gy, h, window):
    """Share of a Gaussian kernel at each cell inside the rectangle (x0, x1, y0, y1), in the same units as h
    (projected coordinates; for lon/lat give the window and cells in km from a reference point)."""
    x0, x1, y0, y1 = window
    gx, gy = np.asarray(gx, float), np.asarray(gy, float)
    return ((norm.cdf((x1 - gx) / h) - norm.cdf((x0 - gx) / h)) *
            (norm.cdf((y1 - gy) / h) - norm.cdf((y0 - gy) / h)))


def lcv_bandwidth(x, y, candidates, lonlat=False):
    x, y = np.asarray(x, float), np.asarray(y, float)
    d2 = _d2(x, y, x, y, lonlat)
    np.fill_diagonal(d2, np.inf)
    scores = []
    for h in candidates:
        f = np.exp(-d2 / (2 * h * h)).sum(1) / ((len(x) - 1) * 2 * np.pi * h * h)
        scores.append(float(np.log(np.maximum(f, 1e-300)).sum()))
    j = int(np.argmax(scores))
    return {"h": float(candidates[j]), "scores": list(zip(map(float, candidates), scores)),
            "at_edge": j in (0, len(candidates) - 1)}


def local_maxima(Z):
    """Cells higher than all eight neighbours (a count of peaks)."""
    Zp = np.pad(Z, 1, constant_values=-np.inf)
    core = Zp[1:-1, 1:-1]
    higher = np.ones(Z.shape, bool)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr or dc:
                higher &= core > Zp[1 + dr:Zp.shape[0] - 1 + dr, 1 + dc:Zp.shape[1] - 1 + dc]
    return int(higher.sum())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("points")
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--x")
    p.add_argument("--y")
    p.add_argument("--crs")
    p.add_argument("--where", default="true")
    p.add_argument("--window", type=float, nargs=4, required=True, metavar=("W", "S", "E", "N"))
    p.add_argument("--cell", type=float, required=True)
    p.add_argument("--h", type=float)
    p.add_argument("--out")
    a = p.parse_args()
    lonlat = bool(a.lon)
    if not (lonlat or (a.x and a.y and a.crs)):
        p.error("give --lon/--lat, or --x/--y with --crs")

    import duckdb

    cx, cy = (a.lon, a.lat) if lonlat else (a.x, a.y)
    rows = duckdb.sql(f'select "{cx}", "{cy}" from \'{a.points}\' where {a.where}').fetchall()
    x, y = np.array([r[0] for r in rows], float), np.array([r[1] for r in rows], float)
    W, S, E, N = a.window
    inside = (x >= W) & (x <= E) & (y >= S) & (y <= N)
    print(f"points {len(x)}, inside the window {int(inside.sum())} (the others are left out)")
    x, y = x[inside], y[inside]
    if a.h:
        h = a.h
    else:
        span = (2 * EARTH_KM * np.radians(max(E - W, N - S)) if lonlat else max(E - W, N - S))
        sel = lcv_bandwidth(x, y, np.geomspace(span / 500, span / 5, 30), lonlat)
        h = sel["h"]
        print("likelihood cross-validation: " + ", ".join(f"{c:.3g} {s:.1f}" for c, s in sel["scores"]))
        if sel["at_edge"]:
            print("the best bandwidth is at the edge of the candidates: widen the range")
    gxs = np.arange(W + a.cell / 2, E, a.cell)
    gys = np.arange(N - a.cell / 2, S, -a.cell)
    GX, GY = np.meshgrid(gxs, gys)
    lam = intensity(x, y, GX.ravel(), GY.ravel(), h, lonlat).reshape(GY.shape)
    if lonlat:  # edge correction on a local plane in km
        lat0 = (S + N) / 2
        kx = np.pi / 180 * EARTH_KM * np.cos(np.radians(lat0))
        ky = np.pi / 180 * EARTH_KM
        mass = edge_mass((GX - W) * kx, (GY - S) * ky, h, (0, (E - W) * kx, 0, (N - S) * ky))
    else:
        mass = edge_mass(GX, GY, h, (W, E, S, N))
    corrected = lam / mass
    unit = "km^2" if lonlat else f"{a.crs} unit^2"
    print(f"bandwidth {h:.4g} {'km' if lonlat else ''}; intensity per {unit}: max {corrected.max():.4g}, "
          f"peaks {local_maxima(corrected)}; edge mass min {mass.min():.2f}")
    if a.out:
        import rasterio
        from rasterio.transform import from_origin

        with rasterio.open(a.out, "w", driver="GTiff", height=lam.shape[0], width=lam.shape[1], count=1,
                           dtype="float64", crs="EPSG:4326" if lonlat else a.crs,
                           transform=from_origin(W, N, a.cell, a.cell)) as ds:
            ds.write(corrected, 1)
            ds.set_band_description(1, f"intensity per {unit}, Gaussian h {h:.4g}, edge-corrected")
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
