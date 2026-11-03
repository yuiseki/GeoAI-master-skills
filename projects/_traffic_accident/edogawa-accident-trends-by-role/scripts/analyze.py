"""Count Edogawa's injury accidents (2019-2025 file years) for the four role reports.

Run from the repository root after prepare.py:
uvx --from 'duckdb>=1.5.5' --with numpy python projects/_traffic_accident/edogawa-accident-trends-by-role/scripts/analyze.py

Reads artifacts/_traffic_accident/edogawa-accident-trends-by-role/*.parquet and writes the tables to outputs/ and
the per-accident points (with EPSG:6677 x, y) to artifacts/.../points.csv.
"""

import csv
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

import duckdb
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
ART = ROOT / "artifacts/_traffic_accident" / PROJECT.name
OUT = PROJECT / "outputs"
# The ward: the NPA 市区町村コード (3 digits) and the jp-admin code5 (13 + the same 3 digits).
CODE = "123"
WARD = f"13{CODE}"
WARD_NAME = "江戸川区"  # as in wards.csv, and the scope of yearly.csv
WARD_CODES = [f"{i:03d}" for i in range(101, 124)]
YEARS = [str(y) for y in range(2019, 2026)]
FIRST_HALF = {"2019", "2020", "2021"}
RADIUS = 30.0
RADII = (20.0, 30.0, 50.0)
TOP = 15
SCHOOL_RADIUS = 500.0
# A hotspot is named by the nearest road and the nearest other road that crosses it: at least this angle between
# their directions within ROAD_STEP metres either side of the point nearest the centre (map-context 13).
MIN_CROSSING_ANGLE = 30.0
ROAD_STEP = 20.0
ROAD_CANDIDATES = 6
# A town with less road than this keeps its rate and colour but is not ranked among the top five (color-and-scale,
# 分母の小さい単位の率): at 0.5 km one accident more moves the rate by 0.29 per km per year. Ota's river bank, 0.134 km
# of road and 7 accidents, ranked first at 7.46. Decided at R013, before looking at the ranks of the wards to come.
MIN_ROAD_KM = 0.5
WATER = "8154"  # HCODE of a census water tract (水面調査区); 8101 is a town (町丁・字等)

STRICT = {"01", "02", "11"}
BROAD = STRICT | {"14", "17"}
PED = {"61"}
BIKE = {"51", "52"}
ESCOOTER = {"43"}
YOUNG = {"01"}
OLD = {"65", "75"}
NIGHT = {"21", "22", "23"}

# Party type code -> group for the A x B matrix. 用途別 01 (事業用) splits passenger cars.
GROUPS = [
    ("歩行者", {"61"}),
    ("自転車", {"51", "52"}),
    ("特定小型原付", {"43"}),
    ("二輪車", {"31", "32", "33", "34", "35", "36"}),
    ("乗用車", {"01", "02", "03", "04", "05", "07"}),
    ("貨物車", {"11", "12", "13", "14", "17"}),
    ("相手なし・物件", {"75", "76"}),
]


def is_seikatsu(width, broad=False):
    """生活道路 by 車道幅員: strict = single road under 5.5 m or small x small crossing."""
    return width in (BROAD if broad else STRICT)


def involves(row, kinds, ages=None):
    """True if party A or B is of one of kinds (and, if given, in one of the age bands)."""
    for side in ("A", "B"):
        if row[f"type_{side}"] in kinds and (ages is None or row[f"age_{side}"] in ages):
            return True
    return False


def party_group(kind, use):
    for name, codes in GROUPS:
        if kind in codes:
            if name == "乗用車":
                return "乗用車 (事業用)" if use == "01" else "乗用車 (自家用)"
            return name
    return "その他・不明"


def neighbours(xy, radius):
    """For each point, the sorted indices of the points within radius (itself included), found through square cells
    of side radius, so that memory grows with the number of near pairs, not with the square of the points."""
    xy = np.asarray(xy, dtype=float)
    cells = np.floor(xy / radius).astype(np.int64)
    by_cell = {}
    for i, c in enumerate(map(tuple, cells)):
        by_cell.setdefault(c, []).append(i)
    by_cell = {c: np.array(v) for c, v in by_cell.items()}
    out = [None] * len(xy)
    for (cx, cy), here in by_cell.items():
        cand = np.sort(np.concatenate([by_cell[(cx + dx, cy + dy)] for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                                       if (cx + dx, cy + dy) in by_cell]))
        # The same arithmetic as a full distance matrix, so a point on the circle is in or out alike.
        near = ((xy[here][:, None, :] - xy[cand][None, :, :]) ** 2).sum(axis=2) <= radius * radius
        for row, i in enumerate(here):
            out[i] = cand[near[row]]
    return out


def greedy_hotspots(xy, radius, k):
    """Pick up to k centres among the points: the point with most points within radius, then drop
    those points and repeat. Returns (index of centre, member indices) pairs; members never overlap.
    Ties go to the lowest index. Ota's 10,335 points took 3.8 GB as an n x n matrix; neighbour lists do not."""
    nb = neighbours(xy, radius)
    alive = np.ones(len(nb), dtype=bool)
    counts = np.array([len(n) for n in nb], dtype=np.int64)
    picked = []
    while len(picked) < k and alive.any():
        centre = int(np.argmax(np.where(alive, counts, -1)))
        members = nb[centre][alive[nb[centre]]]
        picked.append((centre, members))
        # Each removed point leaves the counts of the points near it.
        np.subtract.at(counts, np.concatenate([nb[m] for m in members]), 1)
        alive[members] = False
    return picked


def poisson_interval(n):
    """Exact 95% interval of a Poisson count (Garwood) via the chi-square quantiles."""
    from math import isclose
    lo = 0.0 if n == 0 else chi2_ppf(0.025, 2 * n) / 2
    hi = chi2_ppf(0.975, 2 * n + 2) / 2
    assert not isclose(hi, lo)
    return lo, hi


def chi2_ppf(p, dof):
    """Chi-square quantile by bisection on the regularised gamma function (no scipy)."""
    from math import exp, lgamma, log

    def cdf(x):
        a, s, term, i = dof / 2, 0.0, 0.0, 0
        if x <= 0:
            return 0.0
        term = exp(-x / 2 + a * log(x / 2) - lgamma(a + 1))
        s = term
        while term > 1e-14 * s:
            i += 1
            term *= (x / 2) / (a + i)
            s += term
        return s

    lo, hi = 0.0, dof + 50 * (dof ** 0.5) + 50
    for _ in range(200):
        mid = (lo + hi) / 2
        if cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def ward_ranks(wards, code):
    """Rank (1 = highest) of the ward with this 3-digit code among the rows of wards, for each share_ and per_
    column. Ties share the better rank. Stops if the code is missing or repeated."""
    mine = [w for w in wards if w["code"] == code]
    if len(mine) != 1:
        raise ValueError(f"ward code {code} appears {len(mine)} times in the ward table")
    return {k: 1 + sum(w[k] > mine[0][k] for w in wards)
            for k in mine[0] if k.startswith("share_") or k.startswith("per_")}


def git_head(root):
    """The commit of the working tree, read from the files in .git without running git (a subagent may not run
    git). Follows a worktree's .git file and packed-refs. Returns None if it cannot be read."""
    try:
        git = root / ".git"
        if git.is_file():
            git = (root / git.read_text(encoding="utf-8").split(":", 1)[1].strip()).resolve()
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref: "):
            return head
        ref = head[5:]
        common = git / "commondir"
        base = (git / common.read_text(encoding="utf-8").strip()).resolve() if common.exists() else git
        for d in (git, base):
            if (d / ref).exists():
                return (d / ref).read_text(encoding="utf-8").strip()
        for d in (git, base):
            packed = d / "packed-refs"
            if packed.exists():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line.endswith(" " + ref):
                        return line.split()[0]
    except OSError:
        return None
    return None


def line_angle(u, v):
    """Angle in degrees (0-90) between two undirected lines given as direction vectors; None for a zero vector."""
    nu, nv = math.hypot(*u), math.hypot(*v)
    if nu == 0 or nv == 0:
        return None
    return math.degrees(math.acos(min(1.0, abs(u[0] * v[0] + u[1] * v[1]) / (nu * nv))))


def crossing_road(near):
    """The second name of a hotspot: from (name, distance, direction) sorted by distance, the nearest name after the
    first whose direction crosses the first's by MIN_CROSSING_ANGLE or more. OSM can give one road two names
    (Shinagawa's 環状六号線 and 山手通り), which are not an intersection. (None, None) if no name crosses."""
    if len(near) < 2:
        return None, None
    first = near[0][2]
    for name, dist, direction in near[1:]:
        if direction is None:
            continue
        angle = None if first is None else line_angle(first, direction)
        if first is None or (angle is not None and angle >= MIN_CROSSING_ANGLE):
            return name, dist
    return None, None


def unit_name(key_code, s_name, hcode):
    """The name of a census unit for the tables. Water tracts (HCODE 8154) are named 水面 whatever their S_NAME
    (Chuo 水面調査区, Minato '‐', Koto and Shinagawa empty); a town with no name keeps its code."""
    if hcode == WATER:
        return f"水面 ({key_code})"
    return s_name if s_name else f"名前なし ({key_code})"


def unit_names(pairs):
    """KEY_CODE -> name, with the code added to a name that more than one unit carries (Ota's two 令和島)."""
    seen = Counter(name for _, name in pairs)
    return {code: f"{name} ({code})" if seen[name] > 1 else name for code, name in pairs}


def write_csv(name, rows):
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return str(path.relative_to(ROOT))


def load(con):
    con.sql("load spatial")
    # Every geometry here is (lon, lat) or (easting, northing); EPSG:6677 output is (x = easting, y = northing).
    con.sql("set geometry_always_xy = true")
    con.sql(f"""create table acc as select
        file_year, "市区町村コード" as ward, "警察署等コード" as station, "本票番号" as no,
        cast("死者数" as integer) as died, cast("負傷者数" as integer) as hurt,
        "事故類型" as kind, "道路形状" as shape, "車道幅員" as width, "信号機" as signal,
        "昼夜" as daynight, "天候" as weather, "ゾーン規制" as zone, "歩車道区分" as sidewalk,
        substr("路線コード", 1, 4) as route,
        "当事者種別（当事者A）" as type_A, "当事者種別（当事者B）" as type_B,
        "年齢（当事者A）" as age_A, "年齢（当事者B）" as age_B,
        "用途別（当事者A）" as use_A, "用途別（当事者B）" as use_B,
        "人身損傷程度（当事者A）" as injury_A, "人身損傷程度（当事者B）" as injury_B,
        cast("発生日時　　時" as integer) as hour, cast("曜日(発生年月日)" as integer) as weekday,
        longitude, latitude
        from '{ART / "tokyo_honhyo.parquet"}' where "市区町村コード" in ({",".join(repr(c) for c in WARD_CODES)})""")
    con.sql(f"""create table pts as select *,
        ST_X(ST_Transform(ST_Point(longitude, latitude), 'OGC:CRS84', 'EPSG:6677')) as x,
        ST_Y(ST_Transform(ST_Point(longitude, latitude), 'OGC:CRS84', 'EPSG:6677')) as y
        from acc where ward = '{CODE}' and longitude is not null""")
    cols = [c[0] for c in con.execute("select * from acc limit 0").description]
    return [dict(zip(cols, r)) for r in con.execute("select * from acc").fetchall()]


def flags(row):
    return {
        "ped": involves(row, PED),
        "bike": involves(row, BIKE),
        "escooter": involves(row, ESCOOTER),
        "old_ped": involves(row, PED, OLD),
        "young_pb": involves(row, PED | BIKE, YOUNG),
        "strict": is_seikatsu(row["width"]),
        "broad": is_seikatsu(row["width"], broad=True),
        "night": row["daynight"] in NIGHT,
        "intersection": row["shape"] in {"01", "31"},
    }


def main():
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect()
    rows = load(con)
    for row in rows:
        row.update(flags(row))
    mine = [r for r in rows if r["ward"] == CODE]
    audit = {"rows_23_wards": len(rows), "rows_ward": len(mine),
             "ward_without_point": sum(r["longitude"] is None for r in mine)}

    # Coded ward vs the point in the ward polygon (the alternative reading of "the ward's accidents").
    inside = con.execute(f"""with w as (select ST_GeomFromWKB(geometry) g from '{ART / "wards.parquet"}' where code5 = '{WARD}')
        select count(*) filter (where ward = '{CODE}' and ST_Contains(w.g, ST_Point(longitude, latitude))),
               count(*) filter (where ward = '{CODE}' and not ST_Contains(w.g, ST_Point(longitude, latitude))),
               count(*) filter (where ward <> '{CODE}' and ST_Contains(w.g, ST_Point(longitude, latitude)))
        from acc, w where longitude is not null""").fetchall()[0]
    audit.update(coded_and_inside=inside[0], coded_outside=inside[1], other_code_inside=inside[2])
    # The same by year, so that a change between years can be told from a change in how accidents are coded to a
    # ward (Shibuya, Sumida, Koto and Shinagawa each added this after seeing a jump; it is part of the run now).
    audit["by_year_coded_vs_inside"] = {y: {"coded": c, "inside": n} for y, c, n in con.execute(f"""
        with w as (select ST_GeomFromWKB(geometry) g from '{ART / "wards.parquet"}' where code5 = '{WARD}')
        select file_year, count(*) filter (where ward = '{CODE}'),
               count(*) filter (where longitude is not null and ST_Contains(w.g, ST_Point(longitude, latitude)))
        from acc, w group by file_year order by file_year""").fetchall()}

    # B1 yearly counts, the ward and the 23 wards.
    keys = ["ped", "bike", "escooter", "old_ped", "young_pb", "strict", "broad", "night", "intersection"]
    yearly = []
    for scope, subset in ((WARD_NAME, mine), ("23区", rows)):
        base = sum(r["file_year"] == "2019" for r in subset)
        for y in YEARS:
            ys = [r for r in subset if r["file_year"] == y]
            lo, hi = poisson_interval(len(ys))
            yearly.append({"scope": scope, "year": y, "accidents": len(ys), "lo95": round(lo, 1), "hi95": round(hi, 1),
                           "index_2019": round(100 * len(ys) / base, 1),
                           "died": sum(r["died"] for r in ys), "hurt": sum(r["hurt"] for r in ys),
                           **{k: sum(r[k] for r in ys) for k in keys}})
    files = {"yearly": write_csv("yearly.csv", yearly)}

    # B2 composition of each of the 23 wards (7 years pooled).
    names = dict(con.execute(f"select substr(code5, 3), name from '{ART / 'wards.parquet'}'").fetchall())
    pops = dict(con.execute(f"select substr(code5, 3), population from '{ART / 'wards.parquet'}'").fetchall())
    wards = []
    for code in WARD_CODES:
        ws = [r for r in rows if r["ward"] == code]
        wards.append({"code": code, "name": names[code], "accidents": len(ws), "population_2020": pops[code],
                      "per_1000_residents_per_year": round(1000 * len(ws) / 7 / pops[code], 2),
                      **{f"share_{k}": round(sum(r[k] for r in ws) / len(ws), 4) for k in keys}})
    files["wards"] = write_csv("wards.csv", wards)
    # The ward's rank among the 23 wards (1 = highest share), found by its code (not by its place in the list).
    audit["ward_rank_of_23"] = ward_ranks(wards, CODE)

    # B3 hour x weekday in the ward.
    hours = []
    for group, test in (("全て", lambda r: True), ("若い歩行者・自転車", lambda r: r["young_pb"]),
                        ("高齢の歩行者", lambda r: r["old_ped"]), ("自転車", lambda r: r["bike"])):
        c = Counter((r["weekday"], r["hour"]) for r in mine if test(r))
        hours += [{"group": group, "weekday": wd, "hour": h, "accidents": c[(wd, h)]}
                  for wd in range(1, 8) for h in range(24)]
    files["hours"] = write_csv("hour_weekday.csv", hours)

    # Party A x party B matrix and the deaths.
    matrix = Counter((party_group(r["type_A"], r["use_A"]), party_group(r["type_B"], r["use_B"])) for r in mine)
    files["parties"] = write_csv("party_matrix.csv", [{"party_A": a, "party_B": b, "accidents": n}
                                                       for (a, b), n in sorted(matrix.items(), key=lambda kv: -kv[1])])
    deaths = [{"year": r["file_year"], "type_A": party_group(r["type_A"], r["use_A"]), "age_A": r["age_A"],
               "type_B": party_group(r["type_B"], r["use_B"]), "age_B": r["age_B"], "hour": r["hour"],
               "kind": r["kind"], "died": r["died"],
               "dead_party": "/".join(party_group(r[f"type_{s}"], r[f"use_{s}"]) for s in "AB" if r[f"injury_{s}"] == "1")
               or "補充票の人"} for r in mine if r["died"] > 0]
    files["deaths"] = write_csv("deaths.csv", sorted(deaths, key=lambda d: d["year"]))

    # Road type (route code: 0001-0999 national, 1000-1499 major prefectural, 2000-2999 prefectural,
    # 3000-3999 municipal, 5000-5499 expressway; 9000- private and other).
    def route_class(code):
        n = int(code)
        return ("国道" if n < 1000 else "主要地方道 (都道)" if n < 1500 else "一般都道" if 2000 <= n < 3000
                else "区道" if 3000 <= n < 4000 else "首都高速" if 5000 <= n < 5500 else "その他")
    roads = Counter((r["file_year"], route_class(r["route"])) for r in mine)
    nat = Counter(r["route"] for r in mine if int(r["route"]) < 1000)
    files["route"] = write_csv("route_class.csv", [{"year": y, "route_class": c, "accidents": n}
                                                   for (y, c), n in sorted(roads.items())])
    audit["national_routes"] = dict(nat)

    # Points in EPSG:6677 (JGD2011 plane IX, metres) for the distance work.
    pcols = [c[0] for c in con.execute("select * from pts limit 0").description]
    prow = [dict(zip(pcols, r)) for r in con.execute("select * from pts").fetchall()]
    for p in prow:
        p.update(flags(p))
    with (ART / "points.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["file_year", "weekday", "hour", "longitude", "latitude", "x", "y", *keys, "young_pb"]
        writer = csv.DictWriter(f, fieldnames=list(dict.fromkeys(fields)), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(prow)
    xy = np.array([[p["x"], p["y"]] for p in prow])
    audit["ward_points"] = len(prow)

    # B4 schools: young pedestrians and cyclists within 500 m (straight line).
    schools = con.execute(f"""select name,
        ST_X(ST_Transform(ST_Point(lon, lat), 'OGC:CRS84', 'EPSG:6677')),
        ST_Y(ST_Transform(ST_Point(lon, lat), 'OGC:CRS84', 'EPSG:6677')), lon, lat
        from '{ART / 'schools.parquet'}' order by name""").fetchall()
    young = np.array([p["young_pb"] for p in prow])
    pb = np.array([p["ped"] or p["bike"] for p in prow])
    morning = np.array([p["weekday"] in range(2, 7) and 7 <= p["hour"] <= 8 for p in prow])
    afternoon = np.array([p["weekday"] in range(2, 7) and 14 <= p["hour"] <= 17 for p in prow])
    school_rows = []
    for name, sx, sy, lon, lat in schools:
        near = np.hypot(xy[:, 0] - sx, xy[:, 1] - sy) <= SCHOOL_RADIUS
        school_rows.append({"school": name, "lon": round(lon, 6), "lat": round(lat, 6),
                            "all": int(near.sum()), "ped_or_bike": int((near & pb).sum()),
                            "young_ped_or_bike": int((near & young).sum()),
                            "young_weekday_7_8": int((near & young & morning).sum()),
                            "young_weekday_14_17": int((near & young & afternoon).sum())})
    school_rows.sort(key=lambda s: -s["young_ped_or_bike"])
    files["schools"] = write_csv("schools.csv", school_rows)

    # B5 hotspots: greedy non-overlapping 30 m circles, and the 20 m / 50 m readings.
    road_names = con.execute(f"""select name, ST_AsWKB(ST_Transform(ST_GeomFromWKB(geometry), 'OGC:CRS84', 'EPSG:6677'))
        from '{ART / 'roads.parquet'}' where name is not null and highway not in ('motorway', 'motorway_link')""").fetchall()
    con.sql("create table rn as select * from (values (null::varchar, null::blob)) t(name, g) where false")
    con.executemany("insert into rn values (?, ?)", road_names)
    sets = {}
    for radius in RADII:
        sets[radius] = greedy_hotspots(xy, radius, TOP)
    hot = []
    for rank, (centre, members) in enumerate(sets[RADIUS], 1):
        ms = [prow[i] for i in members]
        cx, cy = xy[centre]
        near = []
        for name, d in con.execute(f"""select name, min(ST_Distance(ST_GeomFromWKB(g), ST_Point({cx}, {cy}))) d from rn
                group by name order by d, name limit {ROAD_CANDIDATES}""").fetchall():
            # The direction of the named road where it passes nearest the centre: its nearest piece, ROAD_STEP m
            # either side of the point nearest the centre.
            ends = con.execute(f"""with pieces as (select unnest(ST_Dump(ST_GeomFromWKB(g))).geom as p from rn where name = ?),
                near as (select p from pieces where ST_GeometryType(p) = 'LINESTRING' and ST_Length(p) > 0
                         order by ST_Distance(p, ST_Point({cx}, {cy})) limit 1),
                loc as (select p, ST_LineLocatePoint(p, ST_Point({cx}, {cy})) f, ST_Length(p) len from near)
                select ST_X(a), ST_Y(a), ST_X(b), ST_Y(b) from (select
                    ST_LineInterpolatePoint(p, greatest(0, f - {ROAD_STEP} / len)) a,
                    ST_LineInterpolatePoint(p, least(1, f + {ROAD_STEP} / len)) b from loc)""", [name]).fetchall()
            near.append((name, d, (ends[0][2] - ends[0][0], ends[0][3] - ends[0][1]) if ends else None))
        near_names = [near[0][0]] if near else []
        second, dist = crossing_road(near)
        # A crossing road farther than RADIUS is not the hotspot's crossing: left empty, so that hotspots.csv read
        # alone does not show an intersection (Nakano's 中野四季の森通り was 253 m away).
        if second is not None and dist <= RADIUS:
            near_names.append(second)
        else:
            dist = None
        routes = Counter(route_class(m["route"]) + (f" {int(m['route'])}号" if int(m["route"]) < 1000 else "") for m in ms)
        combos = Counter(f"{party_group(m['type_A'], m['use_A'])} × {party_group(m['type_B'], m['use_B'])}" for m in ms)
        hot.append({"rank": rank, "lon": round(prow[centre]["longitude"], 6), "lat": round(prow[centre]["latitude"], 6),
                    "x": round(cx, 1), "y": round(cy, 1), "accidents": len(ms),
                    "first_2019_2021": sum(m["file_year"] in FIRST_HALF for m in ms),
                    "second_2022_2025": sum(m["file_year"] not in FIRST_HALF for m in ms),
                    "first_per_year": round(sum(m["file_year"] in FIRST_HALF for m in ms) / 3, 2),
                    "second_per_year": round(sum(m["file_year"] not in FIRST_HALF for m in ms) / 4, 2),
                    "ped": sum(m["ped"] for m in ms), "bike": sum(m["bike"] for m in ms),
                    "intersection": sum(m["intersection"] for m in ms),
                    "signal": sum(m["signal"] in {"1", "2", "8"} for m in ms),
                    "night": sum(m["night"] for m in ms),
                    "top_route": routes.most_common(1)[0][0], "top_route_n": routes.most_common(1)[0][1],
                    "top_combo": combos.most_common(1)[0][0], "top_combo_n": combos.most_common(1)[0][1],
                    # 首都高速 accidents in the circle: where they are most, road_1 names the road under the
                    # viaduct (Katsushika's 11th, 15 of 16 on the expressway, named after a surface road).
                    "expressway": sum(5000 <= int(m["route"]) < 5500 for m in ms),
                    "road_1": near_names[0] if near_names else "",
                    "road_2": near_names[1] if len(near_names) > 1 else "",
                    "road_2_m": round(dist, 1) if dist is not None else None})
    files["hotspots"] = write_csv("hotspots.csv", hot)
    overlap = {}
    for radius in RADII:
        if radius == RADIUS:
            continue
        others = np.array([xy[c] for c, _ in sets[radius]])
        overlap[f"{int(radius)}m"] = int(sum(np.hypot(*(others - xy[c]).T).min() <= RADIUS for c, _ in sets[RADIUS]))
    audit["hotspot_overlap_of_top15_within_30m"] = overlap
    audit["hotspot_counts"] = {f"{int(r)}m": [len(m) for _, m in sets[r]] for r in RADII}
    # The 30 m hotspots without the 首都高速 accidents (route 5000-5499), beside the main reading: an expressway on
    # a viaduct or in a tunnel shares x, y with the road under or over it (Shibuya, Meguro and Nakano each added
    # this reading; it is part of every run now, and is 0 accidents where no expressway runs).
    surface = np.flatnonzero([route_class(p["route"]) != "首都高速" for p in prow])
    no_expr = [(surface[c], surface[m]) for c, m in greedy_hotspots(xy[surface], RADIUS, TOP)]
    others = np.array([xy[c] for c, _ in no_expr])
    overlap["30m_without_expressway"] = int(sum(np.hypot(*(others - xy[c]).T).min() <= RADIUS for c, _ in sets[RADIUS]))
    audit["expressway_points"] = len(prow) - len(surface)
    audit["hotspot_counts_without_expressway"] = [len(m) for _, m in no_expr]
    audit["expressway_in_top15"] = {"accidents": int(sum(route_class(prow[i]["route"]) == "首都高速"
                                                       for _, m in sets[RADIUS] for i in m)),
                                    "per_rank": [int(sum(route_class(prow[i]["route"]) == "首都高速" for i in m))
                                                 for _, m in sets[RADIUS]]}

    # B6 towns: accidents and OSM road length per census small area.
    # A census town (KEY_CODE) can be several rows of the boundary file (Shinjuku's 山吹町 is two; Taito has none),
    # so the rows are merged into one unit per KEY_CODE: the shapes united and the population summed.
    # An empty S_NAME counts as a name here, so a code with one named and one empty row stops too.
    names_per_code = con.execute(f"""select max(n) from (select count(distinct coalesce(S_NAME, '')) n
        from '{ART / 'towns.parquet'}' group by KEY_CODE)""").fetchall()[0][0]
    kinds_per_code = con.execute(f"""select max(n) from (select count(distinct HCODE) n
        from '{ART / 'towns.parquet'}' group by KEY_CODE)""").fetchall()[0][0]
    if names_per_code != 1 or kinds_per_code != 1:
        raise RuntimeError(f"a KEY_CODE has {names_per_code} names or {kinds_per_code} HCODE")
    # Water tracts (HCODE 8154) and towns without a name are named by unit_name (Koto has both; Taito has neither).
    con.create_function("unit_name", unit_name, ["VARCHAR", "VARCHAR", "VARCHAR"], "VARCHAR")
    con.sql(f"""create table towns as select KEY_CODE, unit_name(KEY_CODE, any_value(S_NAME), any_value(HCODE)) as S_NAME,
        any_value(HCODE) as HCODE, sum(JINKO) as JINKO, count(*) as pieces, ST_Transform(ST_Union_Agg(ST_GeomFromWKB(geometry)), 'EPSG:4612', 'EPSG:6677') as g,
        ST_Union_Agg(ST_GeomFromWKB(geometry)) as g_lonlat from '{ART / 'towns.parquet'}' group by KEY_CODE""")
    for code, name in unit_names(con.execute("select KEY_CODE, S_NAME from towns order by KEY_CODE").fetchall()).items():
        con.execute("update towns set S_NAME = ? where KEY_CODE = ?", [name, code])
    audit.update(town_rows=con.execute(f"select count(*) from '{ART / 'towns.parquet'}'").fetchall()[0][0],
                 towns_merged=[n for (n,) in con.execute(
                     "select S_NAME || ' (' || pieces || ')' from towns where pieces > 1 order by S_NAME").fetchall()])
    con.sql(f"""create table road_m as select ST_Transform(ST_GeomFromWKB(geometry), 'OGC:CRS84', 'EPSG:6677') as g,
        highway from '{ART / 'roads.parquet'}'""")
    con.sql("""create table town_counts as select t.KEY_CODE, t.S_NAME, t.HCODE, t.JINKO,
        (select count(*) from pts p where ST_Contains(t.g, ST_Point(p.x, p.y))) as accidents,
        (select count(*) from pts p where ST_Contains(t.g, ST_Point(p.x, p.y))
            and ('61' in (p.type_A, p.type_B))) as ped,
        (select coalesce(sum(ST_Length(ST_Intersection(r.g, t.g))), 0) from road_m r where ST_Intersects(r.g, t.g)) / 1000 as road_km,
        ST_Area(t.g) / 1e6 as area_km2, t.g_lonlat as geometry
        from towns t""")
    # Principle 12 of map-context: name every census town holding each hotspot centre.
    for h in hot:
        h["town"] = con.execute(f"""select coalesce(string_agg(S_NAME, '/' order by S_NAME), '区外')
            from towns where ST_Covers(g, ST_Point({h['x']}, {h['y']}))""").fetchall()[0][0]
    files["hotspots"] = write_csv("hotspots.csv", hot)
    in_towns = con.execute("select sum(accidents) from town_counts").fetchall()[0][0]
    audit.update(points_in_towns=int(in_towns), points_outside_towns=len(prow) - int(in_towns))
    # A town with no OSM road inside it has no denominator: its rate is NoData (null), not inf or 0
    # (Shinjuku's 神楽坂四丁目; Taito has none). A water tract is not a town: NoData too, its accidents counted
    # (Koto's 85 on bridges and wharves).
    audit["towns_without_road"] = [{"name": n, "accidents": int(a)} for n, a in con.execute(
        f"select S_NAME, accidents from town_counts where road_km = 0 and HCODE <> '{WATER}' order by S_NAME").fetchall()]
    audit["water_units"] = [{"key_code": k, "accidents": int(a)} for k, a in con.execute(
        f"select KEY_CODE, accidents from town_counts where HCODE = '{WATER}' order by KEY_CODE").fetchall()]
    rate = f"case when road_km > 0 and HCODE <> '{WATER}' then {{}} end"
    con.sql(f"""copy (select KEY_CODE, S_NAME, JINKO, accidents, ped, road_km, area_km2,
        {rate.format('accidents / 7 / road_km')} as per_road_km_year, geometry from town_counts)
        to '{ART / 'town_counts.parquet'}' (format parquet)""")
    trows = con.execute(f"""select KEY_CODE, S_NAME, JINKO, accidents, ped, round(road_km, 3), round(area_km2, 4),
        {rate.format('round(accidents / 7 / road_km, 3)')} from town_counts
        order by {rate.format('accidents / road_km')} desc nulls last, KEY_CODE""").fetchall()
    files["towns"] = write_csv("towns.csv", [dict(zip(["key_code", "name", "population", "accidents", "ped", "road_km",
                                                        "area_km2", "per_road_km_year"], t)) for t in trows])
    # The top five towns by rate, for classify_map.py --highlight (README) and plot.py; trows is sorted by rate,
    # NoData last. Towns with less than MIN_ROAD_KM of road are left out of the ranking, and listed.
    audit["small_road_units"] = [{"key_code": t[0], "name": t[1], "accidents": t[3], "road_km": t[5],
                                  "per_road_km_year": t[7]} for t in trows if t[7] is not None and t[5] < MIN_ROAD_KM]
    top = [t for t in trows if t[7] is not None and t[5] >= MIN_ROAD_KM][:5]
    audit["town_top5"] = [t[0] for t in top]
    (PROJECT / "tmp").mkdir(exist_ok=True)
    with (PROJECT / "tmp/town-highlights.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "group", "rank"])
        writer.writerows([t[0], "道路あたり上位5", i] for i, t in enumerate(top, 1))

    commit = git_head(ROOT)
    (OUT / "analysis.json").write_text(json.dumps({
        "run_date": str(date.today()), "commit": commit, "duckdb": duckdb.__version__,
        "inputs": {"npa": "yuiseki/npa-traffic-accidents@389500aae5cec45f1311163f70db6a5f05867838",
                   "admin": "yuiseki/jp-admin-2026-09@e6c87b1d7095c17422147962185071a986e13135",
                   "towns": "yuiseki/estat-boundary-2020@823195c40e1055e2c1b3c0a635369f8c82b6c3fb",
                   "osm": "yuiseki/osm-tokyo23-src-2026-08@38f7a5f961b6e33343d82a11152e768c37d22664"},
        "settings": {"year": "file year", "ward": "市区町村コード", "min_road_km": MIN_ROAD_KM, "strict": sorted(STRICT), "broad": sorted(BROAD),
                     "radius_m": RADIUS, "radii_m": RADII, "school_radius_m": SCHOOL_RADIUS, "crs_metric": "EPSG:6677"},
        "audit": audit, "files": files}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
