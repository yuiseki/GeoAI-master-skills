"""Move values counted in source zones onto target zones whose borders differ, and account for every zone.

Area weighting (--method area) assumes the value is spread evenly over each source zone:

    w_st  = area(s ∩ t) / area(s)          the share of source s that lies in target t
    y_t   = Σ_s y_s w_st

Σ_t w_st is the share of the source covered by targets. Less than 1 means part of the source lies where
there is no target (outside the targets, a gap, a missing geometry); that part is not handed to anyone and
is reported as uncovered. More than 1 means targets overlap and hand out the same value twice.

Auxiliary weighting (--method auxiliary) spreads each source by a weight layer instead of its area: polygons
with a weight (building footprints, residential land, finer zones with a count), each assumed even within
itself. A source that holds no weight falls back to its area, and is counted. Give --aux-coverage, the area
where the layer is complete: a source reaching past it also falls back, because there "no weight" means
"not collected", and spreading by the weight would push the whole source into the collected part.

    w_st  = Σ_a q_a area(a ∩ s ∩ t) / area(a)  ÷  Σ_a q_a area(a ∩ s) / area(a)

The kind of value decides what may be moved:
    extensive  a count that splits with area (people, households): moved as above
    ratio      a rate with its numerator and denominator (employed / population): both are moved as counts
               and divided again in each target. Never spread the rate itself.
    intensive  a level with no denominator at hand (mean income, temperature): the area-weighted mean of the
               sources in each target. Weak: it says nothing about how the level varies inside a source.

Areas are measured after projecting to --area-crs (default EPSG:6933, equal area), never in degrees or Web
Mercator. Invalid geometries are repaired with make_valid and counted, apart from those that were valid as
given and became invalid only in the projection. Overlaps among sources, overlaps among
targets and sliver intersections (weight below --sliver) are measured and printed; overlaps larger than
--overlap-tolerance of the total area stop the run (hairline overlaps from digitising do not).

Outputs: one row per target (value, n_sources, target_km2, source_covered_fraction, status: ok, partial or
no_source) and, with --allocation-out, one row per source-target pair (intersection_km2, source_km2, weight,
allocated). The run exits with status 2 when the allocated total differs from the source total by more than
--tolerance (relative), when sources overlap, or when targets overlap. --allow-uncovered accepts a total
that falls short only by the source area outside the targets, which is still reported.

Usage:
    uvx --from 'duckdb>=1.5.5' --with shapely --with pyproj --with pyarrow python areal_interpolate.py \\
        SOURCES SOURCE_ID TARGETS TARGET_ID --source-crs EPSG:4612 --target-crs EPSG:4612 \\
        (--value COL | --kind ratio --numerator COL --denominator COL | --kind intensive --value COL) \\
        [--method area|auxiliary --aux AUX --aux-weight COL --aux-crs CRS --aux-coverage COVER] [--geom geometry] \\
        [--area-crs EPSG:6933] [--allow-uncovered] [--tolerance 0.001] --out targets.parquet \\
        [--allocation-out pairs.parquet]
"""

import argparse
import sys

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyproj
import shapely
from shapely.strtree import STRtree

KINDS = ("extensive", "ratio", "intensive")


def read(path, key, geom, cols):
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    typ = {r[0]: r[1] for r in con.sql(f"describe select * from '{path}'").fetchall()}[geom]
    expr = {"GEOMETRY": f"ST_AsWKB(\"{geom}\")", "VARCHAR": f"ST_AsWKB(ST_GeomFromText(\"{geom}\"))"}.get(
        typ.split("(")[0], f"\"{geom}\"")
    extra = "".join(f", \"{c}\"" for c in cols)
    rows = con.sql(f"select \"{key}\", {expr}{extra} from '{path}'").fetchall()
    ids = [r[0] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{key} in {path} is not unique: {len(ids) - len(set(ids))} duplicate ids")
    geoms = [shapely.from_wkb(bytes(r[1])) if r[1] is not None else None for r in rows]
    vals = {c: [r[2 + i] for r in rows] for i, c in enumerate(cols)}
    return ids, geoms, vals


def prepare(geoms, src_crs, area_crs):
    """Project to the equal-area CRS and repair. Returns the geometries, the number invalid as given, and the
    number that became invalid only when projected (dense boundaries can cross themselves after rounding)."""
    tr = pyproj.Transformer.from_crs(src_crs, area_crs, always_xy=True)
    out, invalid, projected = [], 0, 0
    for g in geoms:
        if g is None or g.is_empty:
            out.append(None)
            continue
        given_ok = g.is_valid
        invalid += not given_ok
        g = shapely.transform(g, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))
        if not g.is_valid:
            projected += given_ok
            g = shapely.make_valid(g)
            g = shapely.union_all([p for p in getattr(g, "geoms", [g]) if p.geom_type in ("Polygon", "MultiPolygon")])
        out.append(g)
    return out, (invalid, projected)


def overlap_area(geoms):
    """Total area where two or more of the geometries overlap (pairwise intersections, in CRS units)."""
    present = [g for g in geoms if g is not None]
    tree = STRtree(present)
    total = 0.0
    for i, j in zip(*tree.query(present, predicate="intersects")):
        if i < j:
            total += shapely.intersection(present[i], present[j]).area
    return total


def interpolate(sources, source_id, targets, target_id, out, source_crs, target_crs, value=None, kind="extensive",
                numerator=None, denominator=None, method="area", aux=None, aux_weight=None, aux_crs=None,
                geom="geometry", area_crs="EPSG:6933", allocation_out=None, allow_uncovered=False,
                tolerance=0.001, sliver=1e-4, aux_coverage=None, overlap_tolerance=1e-6):
    if kind not in KINDS:
        raise SystemExit(f"--kind must be one of {KINDS}")
    cols = [numerator, denominator] if kind == "ratio" else [value]
    if None in cols:
        raise SystemExit("ratio needs --numerator and --denominator; extensive and intensive need --value")
    sid, sg, sv = read(sources, source_id, geom, cols)
    tid, tg, _ = read(targets, target_id, geom, [])
    sg, (s_invalid, s_proj) = prepare(sg, source_crs, area_crs)
    tg, (t_invalid, t_proj) = prepare(tg, target_crs, area_crs)
    if method == "auxiliary":
        if not (aux and aux_weight and aux_crs):
            raise SystemExit("--method auxiliary needs --aux, --aux-weight and --aux-crs")
        _, ag, av = read_aux(aux, geom, aux_weight)
        ag, _ = prepare(ag, aux_crs, area_crs)
        aux_items = [(g, float(w)) for g, w in zip(ag, av) if g is not None and w]
        atree = STRtree([g for g, _ in aux_items]) if aux_items else None
        if aux_coverage:
            _, cg, _ = read_aux(aux_coverage, geom, None)
            cg, _ = prepare(cg, aux_crs, area_crs)
            coverage = shapely.union_all([g for g in cg if g is not None])
        else:
            coverage = None
            print("warning: no --aux-coverage; a source part without auxiliary weight is taken as holding none",
                  file=sys.stderr)
    elif method != "area":
        raise SystemExit("--method must be area or auxiliary")

    t_present = [i for i, g in enumerate(tg) if g is not None]
    ttree = STRtree([tg[i] for i in t_present])
    pairs, fallback, uncovered_sources, slivers = [], 0, 0, 0
    covered_by_source = []
    for s, g in enumerate(sg):
        if g is None:
            covered_by_source.append(0.0)
            uncovered_sources += 1
            continue
        hits = [t_present[k] for k in ttree.query(g, predicate="intersects")]
        inter = {t: shapely.intersection(g, tg[t]) for t in hits}
        inter = {t: x for t, x in inter.items() if x.area > 0}
        if method == "auxiliary":
            inside = coverage is None or shapely.intersection(g, coverage).area >= g.area * (1 - 1e-6)
            weights, used = aux_weights(g, inter, aux_items, atree) if inside else ({}, False)
            fallback += not used
        else:
            weights = {}
        if not weights:
            weights = {t: x.area / g.area for t, x in inter.items()}
        cov = sum(weights.values())
        covered_by_source.append(cov)
        if cov < 1 - 1e-6:
            uncovered_sources += 1
        for t, w in weights.items():
            slivers += w < sliver
            pairs.append((s, t, inter[t].area, g.area, w))

    # allocation
    n_t = len(tg)
    alloc = {c: np.zeros(n_t) for c in cols}
    area_in = np.zeros(n_t)          # target area covered by sources, for intensive means and coverage
    wsum = {c: np.zeros(n_t) for c in cols}
    n_src = np.zeros(n_t, dtype=int)
    for s, t, a, sa, w in pairs:
        n_src[t] += 1
        area_in[t] += a
        for c in cols:
            v = sv[c][s]
            if v is None:
                continue
            if kind == "intensive":
                alloc[c][t] += float(v) * a
                wsum[c][t] += a
            else:
                alloc[c][t] += float(v) * w

    source_total = {c: float(sum(float(v) for v in sv[c] if v is not None)) for c in cols}
    covered = {c: float(sum(float(v) * min(cv, 1.0) for v, cv in zip(sv[c], covered_by_source) if v is not None)) for c in cols}
    report = {"source_rows": len(sid), "target_rows": len(tid), "pairs": len(pairs), "invalid_sources": s_invalid,
              "invalid_targets": t_invalid, "invalid_sources_after_projection": s_proj,
              "invalid_targets_after_projection": t_proj, "empty_sources": sum(g is None for g in sg),
              "empty_targets": sum(g is None for g in tg), "uncovered_sources": uncovered_sources,
              "sliver_pairs": int(slivers), "fallback_sources": fallback,
              "source_overlap_km2": overlap_area(sg) / 1e6, "target_overlap_km2": overlap_area(tg) / 1e6,
              "area_crs": area_crs}
    s_area = sum(g.area for g in sg if g is not None) / 1e6
    t_area_total = sum(g.area for g in tg if g is not None) / 1e6
    ok = (report["source_overlap_km2"] <= overlap_tolerance * s_area
          and report["target_overlap_km2"] <= overlap_tolerance * t_area_total)
    if kind != "intensive":
        c0 = cols[0]
        report["source_total"] = source_total[c0]
        report["allocated_total"] = float(alloc[c0].sum())
        report["uncovered_amount"] = source_total[c0] - covered[c0]
        expected = covered[c0] if allow_uncovered else source_total[c0]
        diff = report["allocated_total"] - expected
        report["relative_difference"] = diff / expected if expected else 0.0
        ok = ok and abs(report["relative_difference"]) <= tolerance
        if kind == "ratio":
            report["source_total_denominator"] = source_total[cols[1]]
            report["allocated_total_denominator"] = float(alloc[cols[1]].sum())
    report["ok"] = bool(ok)

    t_area = np.array([g.area if g is not None else 0.0 for g in tg])
    status = ["no_source" if n_src[t] == 0 else ("partial" if area_in[t] < t_area[t] * (1 - 1e-6) else "ok")
              for t in range(n_t)]
    table = {"target_id": tid, "status": status}
    if kind == "ratio":
        num, den = alloc[cols[0]], alloc[cols[1]]
        table["numerator"] = [float(num[t]) if n_src[t] else None for t in range(n_t)]
        table["denominator"] = [float(den[t]) if n_src[t] else None for t in range(n_t)]
        table["value"] = [float(num[t] / den[t]) if n_src[t] and den[t] else None for t in range(n_t)]
    elif kind == "intensive":
        table["value"] = [float(alloc[value][t] / wsum[value][t]) if wsum[value][t] else None for t in range(n_t)]
    else:
        table["value"] = [float(alloc[value][t]) if n_src[t] else None for t in range(n_t)]
    table["n_sources"] = n_src.tolist()
    table["target_km2"] = (t_area / 1e6).tolist()
    table["source_covered_fraction"] = [float(area_in[t] / t_area[t]) if t_area[t] else None for t in range(n_t)]
    pq.write_table(pa.table(table), out)
    if allocation_out:
        c0 = cols[0]
        pq.write_table(pa.table({
            "source_id": [sid[s] for s, *_ in pairs], "target_id": [tid[t] for _, t, *_ in pairs],
            "intersection_km2": [a / 1e6 for _, _, a, _, _ in pairs], "source_km2": [sa / 1e6 for *_, sa, _ in pairs],
            "weight": [w for *_, w in pairs],
            "allocated": [None if sv[c0][s] is None or kind == "intensive" else float(sv[c0][s]) * w
                          for s, _, _, _, w in pairs]}), allocation_out)
    for k, v in report.items():
        print(f"{k}: {v}")
    counts = {}
    for s in status:
        counts[s] = counts.get(s, 0) + 1
    print("targets: " + "  ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    return report


def read_aux(path, geom, weight):
    con = duckdb.connect()
    con.sql("install spatial; load spatial; install httpfs; load httpfs;")
    typ = {r[0]: r[1] for r in con.sql(f"describe select * from '{path}'").fetchall()}[geom]
    expr = {"GEOMETRY": f"ST_AsWKB(\"{geom}\")", "VARCHAR": f"ST_AsWKB(ST_GeomFromText(\"{geom}\"))"}.get(
        typ.split("(")[0], f"\"{geom}\"")
    w = f"\"{weight}\"" if weight else "null"
    rows = con.sql(f"select {expr}, {w} from '{path}'").fetchall()
    return None, [shapely.from_wkb(bytes(r[0])) if r[0] is not None else None for r in rows], [r[1] for r in rows]


def aux_weights(g, inter, aux_items, atree):
    """Share of the source's weight in each target. Empty when the source holds no weight."""
    if atree is None:
        return {}, False
    in_source = 0.0
    per_target = {t: 0.0 for t in inter}
    for k in atree.query(g, predicate="intersects"):
        a, q = aux_items[k]
        part = shapely.intersection(a, g)
        if part.area <= 0:
            continue
        in_source += q * part.area / a.area
        for t, x in inter.items():
            if part.intersects(x):
                per_target[t] += q * shapely.intersection(part, x).area / a.area
    if in_source <= 0:
        return {}, False
    return {t: v / in_source for t, v in per_target.items()}, True


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sources")
    p.add_argument("source_id")
    p.add_argument("targets")
    p.add_argument("target_id")
    p.add_argument("--source-crs", required=True)
    p.add_argument("--target-crs", required=True)
    p.add_argument("--kind", default="extensive", choices=KINDS)
    p.add_argument("--value")
    p.add_argument("--numerator")
    p.add_argument("--denominator")
    p.add_argument("--method", default="area", choices=("area", "auxiliary"))
    p.add_argument("--aux")
    p.add_argument("--aux-weight")
    p.add_argument("--aux-crs")
    p.add_argument("--aux-coverage", help="polygons where the auxiliary layer is complete (in --aux-crs)")
    p.add_argument("--overlap-tolerance", type=float, default=1e-6)
    p.add_argument("--geom", default="geometry")
    p.add_argument("--area-crs", default="EPSG:6933")
    p.add_argument("--allow-uncovered", action="store_true")
    p.add_argument("--tolerance", type=float, default=0.001)
    p.add_argument("--sliver", type=float, default=1e-4)
    p.add_argument("--out", required=True)
    p.add_argument("--allocation-out")
    a = p.parse_args()
    rep = interpolate(a.sources, a.source_id, a.targets, a.target_id, a.out, a.source_crs, a.target_crs, a.value,
                      a.kind, a.numerator, a.denominator, a.method, a.aux, a.aux_weight, a.aux_crs, a.geom,
                      a.area_crs, a.allocation_out, a.allow_uncovered, a.tolerance, a.sliver, a.aux_coverage,
                      a.overlap_tolerance)
    if not rep["ok"]:
        print("not conserved, or zones overlap: see the report above", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
