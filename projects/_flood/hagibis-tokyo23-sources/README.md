# hagibis-tokyo23-sources

令和元年東日本台風 (令和元年台風第 19 号、2019-10-12〜13) について、東京 23 区の区、東京都、国土交通省、気象庁が公表した資料を集め、浸水の被害、浸水した所と原因、避難、検証の報告、浸水範囲の地図の有無を、出典つきで表にしたもの。SAR の検証 ([../hagibis-tokyo-sar-flood-record](../hagibis-tokyo-sar-flood-record/)) の正解の材料を探すために作った。

- 報告: [report.md](report.md)
- 東京都の報からの転記: [outputs/tokyo_sources.csv](outputs/tokyo_sources.csv)
- 区ごとの資料: [outputs/ward_sources.csv](outputs/ward_sources.csv)、要約 [outputs/ward_notes.md](outputs/ward_notes.md)
- 浸水実績図との並べ: [outputs/record_vs_reports.csv](outputs/record_vs_reports.csv) ([scripts/01_record_vs_reports.py](scripts/01_record_vs_reports.py))
- 取得した PDF: `artifacts/_flood/hagibis-tokyo23-sources/raw/docs/` (CSV の local_file と sha256)

列: ward, topic (damage, flooded_area, cause, evacuation, verification_report, map_or_gis, timeline, none_found), fact, quote, as_of, source_title, publisher, source_type (ward, tokyo, mlit, jma, other_official, wikipedia, news), url, local_file, sha256, checked_on。

## 再実行

```sh
cd projects/_flood/hagibis-tokyo23-sources
uvx --with duckdb==1.5.5 python scripts/01_record_vs_reports.py
```

資料の検索と転記は手作業 (2026-11-03)。数は資料に書かれたとおりで、計算や推定はしていない。
