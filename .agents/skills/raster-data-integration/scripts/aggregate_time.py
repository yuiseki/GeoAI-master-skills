"""Aggregate a stack of time slices of one raster (monthly, daily, dekadal) to a period, pixel by pixel.

Each slice covers a time interval [start, end). What its value means decides the arithmetic, and must be given:
    accumulation  an amount over the slice (precipitation in mm per month): the slice's amounts are added; a
                  slice that only partly overlaps the period adds its share of the time, which assumes the
                  amount was spread evenly within the slice
    rate          an amount per day, averaged over the slice (mm/day): rate x overlapping days, added
    state         a mean level over the slice (monthly mean temperature): mean weighted by overlapping time

Time is weighted by real durations, so months of 28 to 31 days, leap years and slices of unequal length
(dekads of 10 and 11 days) are counted as they are. Timestamps must carry a time zone; a day in UTC is not a
day in Japan.

coverage is the share of the period covered by a slice with a valid value at that pixel. Missing slices,
gaps between slices and NoData pixels all lower it. Where coverage is below --min-coverage (default 1) the
value is NaN, not a smaller sum. Below 1, an accumulation or rate is the sum over the covered time only; it is
not scaled up.

Usage:
    uvx --with numpy --with rasterio python aggregate_time.py SLICES.csv --kind accumulation|rate|state \\
        --start 2023-01-01T00:00:00+09:00 --end 2024-01-01T00:00:00+09:00 [--min-coverage 1] --out year.tif
SLICES.csv has columns path, start, end (ISO 8601 with a time zone). All slices must share one grid. The
output has two bands: the value, and the coverage.
"""

import argparse
import csv
from datetime import datetime, timezone

import numpy as np

KINDS = ("accumulation", "rate", "state")
DAY = 86400.0


def months(year, tz=timezone.utc):
    """Start and end of each calendar month of a year, in the given time zone."""
    starts = [datetime(year, m, 1, tzinfo=tz) for m in range(1, 13)]
    return starts, starts[1:] + [datetime(year + 1, 1, 1, tzinfo=tz)]


def _aware(t):
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(f"timestamp without a time zone: {t}")
    return t


def aggregate_period(values, starts, ends, kind, p0, p1, min_coverage=1.0):
    """values: array (T, H, W), NaN where a pixel has no value. Returns value and coverage, both (H, W)."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    p0, p1 = _aware(p0), _aware(p1)
    period = (p1 - p0).total_seconds()
    if period <= 0:
        raise ValueError("the period must end after it starts")
    v = np.asarray(values, float)
    total = np.zeros(v.shape[1:])
    weight = np.zeros(v.shape[1:])
    covered = np.zeros(v.shape[1:])
    for x, a, b in zip(v, starts, ends):
        a, b = _aware(a), _aware(b)
        length = (b - a).total_seconds()
        if length <= 0:
            raise ValueError(f"slice ends before it starts: {a} to {b}")
        over = (min(b, p1) - max(a, p0)).total_seconds()
        if over <= 0:
            continue
        ok = np.isfinite(x)
        if kind == "accumulation":
            total[ok] += x[ok] * over / length
        elif kind == "rate":
            total[ok] += x[ok] * over / DAY
        else:
            total[ok] += x[ok] * over
            weight[ok] += over
        covered[ok] += over
    coverage = covered / period
    if np.any(coverage > 1 + 1e-9):
        raise ValueError("slices overlap each other within the period")
    if kind == "state":
        with np.errstate(invalid="ignore", divide="ignore"):
            value = total / weight
    else:
        value = total
    value = np.where((coverage >= min_coverage - 1e-12) & (covered > 0), value, np.nan)
    return {"value": value, "coverage": coverage}


def main(argv=None):
    import rasterio

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("slices")
    p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--start", required=True, type=datetime.fromisoformat)
    p.add_argument("--end", required=True, type=datetime.fromisoformat)
    p.add_argument("--min-coverage", type=float, default=1.0)
    p.add_argument("--band", type=int, default=1)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    with open(a.slices, newline="") as f:
        rows = list(csv.DictReader(f))
    layers, starts, ends, profile = [], [], [], None
    for r in rows:
        with rasterio.open(r["path"]) as ds:
            x = ds.read(a.band, masked=True).astype("float64")
            x = x * ds.scales[a.band - 1] + ds.offsets[a.band - 1]
            grid = (ds.crs, ds.transform, ds.shape)
            if profile is None:
                profile, first = ds.profile, grid
            elif grid != first:
                raise SystemExit(f"{r['path']} is not on the same grid as {rows[0]['path']}")
        layers.append(x.filled(np.nan))
        starts.append(datetime.fromisoformat(r["start"]))
        ends.append(datetime.fromisoformat(r["end"]))
    res = aggregate_period(np.stack(layers), starts, ends, a.kind, a.start, a.end, a.min_coverage)
    profile.update(count=2, dtype="float64", nodata=np.nan)
    with rasterio.open(a.out, "w", **profile) as d:
        d.write(res["value"], 1)
        d.write(res["coverage"], 2)
    cov = res["coverage"]
    print(f"slices {len(rows)}, pixels {cov.size}, with a value {int(np.isfinite(res['value']).sum())}, "
          f"coverage min {cov.min():.3f} median {np.median(cov):.3f}")


if __name__ == "__main__":
    main()
