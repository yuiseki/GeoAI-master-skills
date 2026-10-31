"""How strong a label the 冠水想定箇所 points give the underpasses of mlit-underpass.

uvx --from 'duckdb>=1.5.5' python evals/curriculum/dry-runs/underpass-pilots/kansui_labels.py

Reads three pinned Hugging Face revisions and prints JSON:
- for each underpass, the distance to the nearest 冠水想定箇所 point (great circle, metres), counted in the
  prefectures that have a KML and in those that have none;
- for the 冠水想定箇所 points, how many carry a sign of past flooding or of equipment in the 箇所表 PDF text.

A sign is read from the PDF text as read (no reading of photographs or maps). The free text is `remarks` and
the values (not the keys) of the Hokuriku form's descriptive cells. "record" is 冠水実績, 冠水履歴, or a year or
a typhoon next to 冠水, unless the text says there was none (冠水実績無, 冠水実績なし, 冠水解消). "pump",
"sensor" and "warning" are the equipment the text names; on the Hokuriku form "pump" is also 排水ポンプの有無
= 有. "deep" is the Hokuriku form's 1m以上の冠水の有無 = 有. Signs are counted only for points whose PDF is their
own (`pdf_match` = pdf_unique), because a shared PDF does not say which record is which point.
"""
import json

import duckdb

UP = "hf://datasets/yuiseki/mlit-underpass@4d00072aa88696cfa7026c4cef7d600bc96f9f13/parquet/national.parquet"
KP = "hf://datasets/yuiseki/mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f6a3278a9956044094acd852a73c5283f2/parquet/kansui_points.parquet"
PDF = "hf://datasets/yuiseki/mlit-kansui-flood-prone-points-pdf-jp-2026-09@34e24d0c94dbeec34a45dba934675ec1a1cf0a97/parquet"

RECORD = r"冠水実績|冠水履歴|浸水実績|(H|Ｈ|平成|令和|R|Ｒ|昭和|S|Ｓ)\s*[0-9０-９元]+\s*(年|\.|．).{0,20}冠水|台風.{0,10}冠水|冠水.{0,10}(19|20)[0-9]{2}"
NONE = r"冠水実績(は)?(無|なし|ない)|冠水解消"
HRR_TEXT = ["注意喚起方法", "情報入手方法", "冠水原因", "冠水範囲", "その他"]
SIGNS = {
    "record": f"regexp_matches(txt, '{RECORD}') and not regexp_matches(txt, '{NONE}')",
    "pump": "(regexp_matches(txt, 'ポンプ') or regexp_matches(hrr_pump, '^(有|あり)'))",
    "sensor": "regexp_matches(txt, '水位センサ|冠水センサ|水位計')",
    "warning": "regexp_matches(txt, '警報|情報板|電光|表示板')",
    "deep": "regexp_matches(hrr_deep, '^(有|あり)')",
}


def main():
    c = duckdb.connect()
    c.execute("load spatial")
    c.execute("set geometry_always_xy = true")
    c.execute(f"create table u as select id, pref, lon, lat from '{UP}'")
    c.execute(f"create table k as select fid, pref, lon, lat from '{KP}'")
    c.execute(f"""create table p as select pp.fid, pp.pdf_match, r.layout, r.parse_status,
            concat_ws(' ', r.remarks, {", ".join(f"json_extract_string(r.extra_cells, '$.\"{k}\"')" for k in HRR_TEXT)}) txt,
            coalesce(json_extract_string(r.extra_cells, '$."排水ポンプの有無"'), '') hrr_pump,
            coalesce(json_extract_string(r.extra_cells, '$."1m以上の冠水の有無"'), '') hrr_deep
        from '{PDF}/point_pdf.parquet' pp left join '{PDF}/pdf_records.parquet' r using (pdf_key)""")
    c.execute("""create table d as select u.id, u.pref, (u.pref in (select pref from k)) kml_pref,
            min(st_distance_sphere(st_point(u.lon, u.lat), st_point(k.lon, k.lat))) dist,
            arg_min(k.fid, st_distance_sphere(st_point(u.lon, u.lat), st_point(k.lon, k.lat))) fid
        from u join k on abs(u.lat - k.lat) < 0.05 and abs(u.lon - k.lon) < 0.05 group by all""")
    out = {"underpasses": c.execute("select count(*) from u").fetchone()[0],
           "kansui_points": c.execute("select count(*) from k").fetchone()[0]}
    out["underpasses_in_kml_prefs"] = c.execute("select count(*) from u where pref in (select pref from k)").fetchone()[0]
    out["prefs_without_kml"] = c.execute(
        "select pref, count(*) from u where pref not in (select pref from k) group by 1 order by 2 desc").fetchall()
    out["near"] = {f"{m}m": c.execute(f"select count(*) from d where kml_pref and dist <= {m}").fetchone()[0]
                   for m in (10, 30, 100, 300)}
    out["near_outside_kml_prefs_100m"] = c.execute("select count(*) from d where not kml_pref and dist <= 100").fetchone()[0]
    out["kansui_with_underpass_30m"] = c.execute("""select count(distinct k.fid) from k join u
        on abs(u.lat - k.lat) < 0.01 and abs(u.lon - k.lon) < 0.01
        and st_distance_sphere(st_point(u.lon, u.lat), st_point(k.lon, k.lat)) <= 30""").fetchone()[0]
    out["pdf_match"] = dict(c.execute("select pdf_match, count(*) from p group by 1 order by 2 desc").fetchall())
    base = "from p where pdf_match = 'pdf_unique' and parse_status is not null and parse_status <> 'layout_unknown'"
    out["readable_own_pdf"] = c.execute(f"select count(*) {base}").fetchone()[0]
    out["signs"] = {s: c.execute(f"select count(*) {base} and {e}").fetchone()[0] for s, e in SIGNS.items()}
    out["said_none"] = c.execute(f"select count(*) {base} and regexp_matches(txt, '{NONE}')").fetchone()[0]
    out["any_record_or_deep"] = c.execute(
        f"select count(*) {base} and ({SIGNS['record']} or {SIGNS['deep']})").fetchone()[0]
    out["record_or_deep_by_pref"] = c.execute(f"""select k.pref, count(*) filter (where {SIGNS['record']} or {SIGNS['deep']}),
            count(*)
        from p join k using (fid) where pdf_match = 'pdf_unique' and parse_status <> 'layout_unknown'
        group by 1 having count(*) filter (where {SIGNS['record']} or {SIGNS['deep']}) > 0 order by 2 desc""").fetchall()
    # underpasses whose nearest point within 30 m has its own readable PDF, and the signs of that point
    c.execute(f"""create table up30 as select d.id, p.* exclude (fid) from d join p using (fid)
        where d.kml_pref and d.dist <= 30 and p.pdf_match = 'pdf_unique' and p.parse_status <> 'layout_unknown'""")
    out["underpass_30m_readable"] = c.execute("select count(*) from up30").fetchone()[0]
    out["underpass_30m_signs"] = {s: c.execute(f"select count(*) from up30 where {e}").fetchone()[0]
                                  for s, e in SIGNS.items()}
    out["underpass_30m_record_or_deep"] = c.execute(
        f"select count(*) from up30 where {SIGNS['record']} or {SIGNS['deep']}").fetchone()[0]
    out["record_examples"] = [r[0][:120] for r in c.execute(
        f"select txt {base} and {SIGNS['record']} order by fid limit 8").fetchall()]
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
