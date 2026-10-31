"""Draw the municipality share by region, on one fixed scale, numbering the five largest counts.

uv run --no-project --with duckdb --with numpy --with scipy --with shapely --with matplotlib \
  python3 projects/_traffic_bus/japan-bus-operator-concentration-replication/scripts/regional_maps.py
"""

import csv
import json
import subprocess
import sys

from analysis import ARTIFACTS, PROJECT, url
from plot import DRAW, map_share

PREFECTURES = "https://huggingface.co/datasets/yuiseki/jp-admin-2026-09/resolve/e6c87b1d7095c17422147962185071a986e13135/prefectures.parquet"
# (slug, name, prefecture codes, drawn box xmin ymin xmax ymax or None). Boxes drop far islands
# that would shrink the main land to a corner; the dropped municipalities are listed in the JSON.
REGIONS = [
    ("hokkaido", "北海道", range(1, 2), None),
    ("tohoku", "東北", range(2, 8), None),
    ("kanto", "関東", range(8, 15), (138.3, 34.6, 141.0, 37.2)),
    ("chubu", "中部", range(15, 24), None),
    ("kinki", "近畿", range(24, 31), None),
    ("chugoku", "中国", range(31, 36), None),
    ("shikoku", "四国", range(36, 40), None),
    ("kyushu", "九州", range(40, 47), (128.5, 30.0, 132.2, 34.8)),
    ("okinawa", "沖縄", range(47, 48), (122.8, 24.0, 128.5, 27.0)),
]
TOP = 5
# Zooms for regions whose numbers crowd each other or a prefecture name: xmin xmax ymin ymax, corner.
INSETS = {
    "kanto": ((139.35, 139.95, 35.2, 35.75), "lower right"),
    "kinki": ((134.95, 135.75, 34.45, 34.95), "lower left"),
    "chugoku": ((132.2, 132.85, 34.2, 34.7), "upper left"),
    "okinawa": ((127.6, 127.9, 26.1, 26.45), "upper left"),
}
VALUE = "割合"


def pref_codes(region):
    return [f"{p:02d}" for p in region[2]]


def top_by_count(rows, n=TOP):
    """The n municipalities with the most people aged 65+ in single-operator meshes, ties by code."""
    ranked = sorted((r for r in rows if int(r["single_older_population"]) > 0),
                    key=lambda r: (-int(r["single_older_population"]), r["code5"]))
    return [(i + 1, r) for i, r in enumerate(ranked[:n])]


def main():
    import duckdb

    with (PROJECT / "outputs/municipalities.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial")
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute("CREATE TEMP TABLE metric (code5 VARCHAR, share_pct DOUBLE)")
    con.executemany("INSERT INTO metric VALUES (?, ?)", [(r["code5"], map_share(r)) for r in rows])
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    admin = ARTIFACTS / "admin_units.parquet"
    if not admin.exists():
        con.execute(f"COPY (SELECT code5, name, pref_code, geometry FROM read_parquet(?) "
                    f"WHERE ward IS NULL AND geometry IS NOT NULL) TO '{admin}' (FORMAT PARQUET)", [url("admin")])
    prefs = ARTIFACTS / "prefectures.parquet"
    if not prefs.exists():
        con.execute(f"COPY (SELECT pref_code, pref, geometry FROM read_parquet(?)) TO '{prefs}' (FORMAT PARQUET)", [PREFECTURES])
    seen = set()
    record = []
    for region in REGIONS:
        slug, name, _, box = region
        codes = pref_codes(region)
        seen.update(codes)
        inlist = ", ".join(f"'{c}'" for c in codes)
        clip = "geometry" if box is None else f"ST_Intersection(geometry, ST_MakeEnvelope({box[0]}, {box[1]}, {box[2]}, {box[3]}))"
        table = ARTIFACTS / f"region_{slug}.parquet"
        con.execute(
            f"COPY (SELECT * FROM (SELECT m.code5, m.name, x.share_pct AS \"{VALUE}\", {clip} AS geometry FROM '{admin}' m "
            f"LEFT JOIN metric x USING (code5) WHERE m.pref_code IN ({inlist})) WHERE NOT ST_IsEmpty(geometry) "
            f"ORDER BY code5) TO '{table}' (FORMAT PARQUET)")
        drawn = {c for (c,) in con.execute(f"SELECT code5 FROM '{table}'").fetchall()}
        dropped = con.execute(f"SELECT code5, name FROM '{admin}' WHERE pref_code IN ({inlist}) ORDER BY code5").fetchall()
        dropped = [{"code5": c, "name": n} for c, n in dropped if c not in drawn]
        local = [r for r in rows if r["code5"][:2] in codes]
        top = top_by_count(local)
        if any(r["code5"] not in drawn for _, r in top):
            raise ValueError(f"{name}: a top municipality falls outside the drawn box")
        highlight = PROJECT / f"outputs/region-{slug}-top.csv"
        with highlight.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("id", "group", "rank", "name", "single_older_population", "share_pct"))
            for rank, r in top:
                writer.writerow((r["code5"], f"人数の上位 {TOP}", rank, r["name"], r["single_older_population"], f"{map_share(r):.1f}"))
        image = PROJECT / f"outputs/region-{slug}.png"
        subprocess.run([
            sys.executable, str(DRAW), str(table), "code5", VALUE,
            "--kind", "rate", "--unit", "%（停留所圏の65歳以上人口）",
            "--method", "fixed", "--thresholds", "20", "40", "60", "80",
            "--palette", "YlOrRd", "--crs", "EPSG:4612", "--edges", "on",
            "--source", "P11 2022 (442223b)・国勢調査2020メッシュ (6c486c8)・行政界 (e6c87b1)",
            "--title", f"{name}: 事業者名が1種類のメッシュに住む65歳以上の割合 (番号は人数の上位{TOP})",
            "--context", str(prefs), "--context-name", "pref", "--context-where", f"pref_code IN ({inlist})",
            "--context-crs", "EPSG:4612", "--context-source", "jp-admin-2026-09 e6c87b1 prefectures",
            "--highlight", str(highlight), "--expect-units", str(len(drawn)), "--no-labels", "--png", str(image),
        ] + (["--inset", *map(str, INSETS[slug][0]), "--inset-at", INSETS[slug][1]] if slug in INSETS else []), check=True)
        meta = json.loads(image.with_suffix(".json").read_text(encoding="utf-8"))
        single = sum(int(r["single_older_population"]) for r in local)
        stop = sum(int(r["stop_older_population"]) for r in local)
        record.append({"region": name, "units": len(drawn), "dropped_outside_box": dropped,
                       "single_older_population": single, "stop_older_population": stop,
                       "no_stop_older_population": sum(int(r["no_stop_older_population"]) for r in local),
                       "share_pct": round(100 * single / stop, 1),
                       "top": [{"rank": k, "name": r["name"], "single_older_population": int(r["single_older_population"]),
                                "share_pct": round(map_share(r), 1)} for k, r in top],
                       "units_per_class": meta.get("units_per_class"), "nodata_units": meta.get("nodata_units"),
                       "text_overlaps": meta.get("text_overlaps"),
                       "zoomed_in_inset": meta.get("zoomed_in_inset"), "hidden_by_inset": meta.get("hidden_by_inset")})
    audit = json.loads((PROJECT / "outputs/audit.json").read_text(encoding="utf-8"))["radii"]["800"]
    if sum(r["single_older_population"] for r in record) != audit["single_older_population"]:
        raise ValueError("regional totals do not add up to the national total")
    if seen != {f"{p:02d}" for p in range(1, 48)}:
        raise ValueError("regions do not cover the 47 prefectures exactly")
    (PROJECT / "outputs/regions.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
