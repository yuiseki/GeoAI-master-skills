"""Pycnophylactic interpolation (Tobler 1979) on a grid: a smooth surface whose sum over every source zone is
that zone's count, then summed over target zones.

    start      each zone's count spread evenly over its cells
    iterate    smooth (each cell towards the mean of its four neighbours, relaxed: r x old + (1 - r) x smoothed);
               shift each zone's cells by a common amount so the zone sums to its count; set negatives to 0;
               scale each zone's cells so it sums to its count again; stop when no cell moves by more than
               10^-converge x the starting maximum
    edges      "neumann" (default): a cell outside the study area or beyond the grid is left out of its
               neighbours' mean. "mean": the grid is padded with the mean of the cells and cells outside the
               study area count as 0 in the neighbour mean, as tobler's pycno does with handle_null=False (kept
               to reproduce it; it pulls cells next to a gap towards 0)

The surface is a guess, not data: it is smooth by construction and has no information inside a zone beyond its
neighbours' counts. It suits counts that change gradually across zone borders (population density in a
continuous city) and misplaces counts that sit in one corner of a zone or change sharply at its border.

Input here is a grid of zone labels (each cell's source zone, -1 outside), as when the zones are cells of a
coarser grid or have been rasterised. Every cell has the same area.
"""

import numpy as np


def _neighbour_mean(v, valid, edge):
    if edge == "neumann":
        s = np.zeros_like(v)
        k = np.zeros_like(v)
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(v, (dr, dc), axis=(0, 1))
            ok = np.roll(valid, (dr, dc), axis=(0, 1))
            if dr == 1:
                ok[0, :] = False
            if dr == -1:
                ok[-1, :] = False
            if dc == 1:
                ok[:, 0] = False
            if dc == -1:
                ok[:, -1] = False
            s += np.where(ok, shifted, 0.0)
            k += ok
        return np.where(k > 0, s / np.maximum(k, 1), v)
    if edge == "mean":
        p = np.pad(np.where(valid, v, 0.0), 1, constant_values=v[valid].mean())
        p[1:-1, 1:-1][~valid] = 0.0
        return (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
    raise ValueError("edge is neumann or mean")


def pycno(zones, totals, r=0.2, converge=3, edge="neumann", max_iter=10_000):
    """zones: 2-d int array of source labels (-1 outside); totals: {label: count}. Returns the surface (NaN
    outside) and the number of iterations."""
    zones = np.asarray(zones)
    valid = zones >= 0
    labels = [z for z in np.unique(zones[valid])]
    missing = [z for z in labels if z not in totals]
    if missing:
        raise SystemExit(f"{len(missing)} zones have cells but no count, e.g. {missing[:3]}")
    masks = {z: zones == z for z in labels}
    n_cells = {z: int(m.sum()) for z, m in masks.items()}
    v = np.zeros(zones.shape)
    for z, m in masks.items():
        v[m] = totals[z] / n_cells[z]
    stopper = v[valid].max() * 10.0 ** -converge
    for it in range(1, max_iter + 1):
        old = v.copy()
        v = r * v + (1 - r) * _neighbour_mean(v, valid, edge)
        for z, m in masks.items():
            v[m] += (totals[z] - v[m].sum()) / n_cells[z]
        v[valid & (v < 0)] = 0.0
        for z, m in masks.items():
            s = v[m].sum()
            if s > 0:
                v[m] *= totals[z] / s
        v[~valid] = 0.0
        if np.abs(v - old)[valid].max() < stopper:
            break
    out = np.where(valid, v, np.nan)
    return out, it


def to_targets(surface, targets):
    """Sum of the surface over each target label (2-d int array, -1 for none)."""
    targets = np.asarray(targets)
    ok = (targets >= 0) & np.isfinite(surface)
    return {int(t): float(surface[ok & (targets == t)].sum()) for t in np.unique(targets[targets >= 0])}


def area_weighted(zones, totals, targets):
    """The even-spread baseline on the same grid: each source's count split by its cells' shares."""
    zones = np.asarray(zones)
    v = np.zeros(zones.shape)
    for z in np.unique(zones[zones >= 0]):
        m = zones == z
        v[m] = totals[z] / m.sum()
    return to_targets(np.where(zones >= 0, v, np.nan), targets)
