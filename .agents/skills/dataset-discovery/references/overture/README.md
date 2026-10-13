# Overture Maps

全世界の地図データ。行政区域、道路と交差点、POI、建物、住所、土地被覆と土地利用、水域。OpenStreetMap などを元に Overture Maps Foundation が月に 1 回ほど版を出す。

| ファイル | テーマ | 中身 |
|---|---|---|
| [divisions.md](divisions.md) | divisions | 国から町丁目までの行政区域の点、面、境界線 |
| [transportation.md](transportation.md) | transportation | 道路と鉄道の線 (segment) と交差点 (connector) |

places (POI)、buildings (建物)、addresses、base はまだ書いていない (TODO.md)。

## 目録の引き方

STAC の静的カタログ。`https://stac.overturemaps.org/catalog.json` が版の一覧 (2026-10-10 には `2026-08-19.0`、`2026-09-23.0`、`2026-09-23.1`)。

```
catalog.json                                  版の一覧
<版>/catalog.json                             テーマの一覧 (addresses、base、buildings、divisions、places、transportation)
<版>/<テーマ>/catalog.json                    種類の一覧 (divisions なら division、division_area、division_boundary)
<版>/<テーマ>/<種類>/collection.json          行数、列、ライセンス、Parquet の置き場所、ファイル (item) の一覧
<版>/<テーマ>/<種類>/<番号>/<番号>.json       1 ファイルの item。範囲 (bbox)、行数、S3 と Azure の URL
```

- collection.json の `table:row_count` が行数、`table:columns` が列、`license` がライセンス、`partition:glob` が Parquet の置き場所。
- item ごとに範囲 (`bbox`) がある。範囲で読むファイルを先に絞れる。transportation/segment は 128 ファイルあり、台東区の付近に重なるのは 4 ファイルだった。
- 版を必ず書く。版ごとに id は保たれるとされるが、行は足され、消され、直される (この保たれ方は確かめていない)。

## 読み方

Parquet は S3 (`s3://overturemaps-us-west-2/release/<版>/theme=<テーマ>/type=<種類>/*.parquet`、リージョン us-west-2、認証なし) と Azure に同じものがある。DuckDB で直接読める。

```sql
load spatial; load httpfs; set s3_region = 'us-west-2';
select id, subtype, class, geometry
from read_parquet('s3://overturemaps-us-west-2/release/2026-09-23.1/theme=transportation/type=segment/*.parquet')
where bbox.xmin <= 139.82 and bbox.xmax >= 139.76 and bbox.ymin <= 35.73 and bbox.ymax >= 35.69;
```

- 各行の範囲は `bbox` 列 (xmin、xmax、ymin、ymax) にある。これで絞ると、Parquet の行グループの統計で読まない部分を飛ばせる。
- `geometry` の CRS 名は `OGC:CRS84`。Natural Earth (`EPSG:4326`) と空間結合するには、spatial-data-integration の references/duckdb-spatial.md のとおり名前を揃える。
- 速さ (2026-10-10、この環境から): 台東区付近 (経度 0.06 度 × 緯度 0.04 度) の道路 24,170 本を、範囲の重なる 4 ファイルから bbox で絞って読むのに 97 秒。divisions/division の 470 万行のうち 10 列を全て読むのに 111 秒。division_area の日本の行の数え上げは 10 秒。
- 列名 `primary` は SQL の予約語なので、`names."primary"` と引用する。

## ライセンス

種類ごとに collection.json の `license` が違う。divisions と transportation は ODbL-1.0 (OpenStreetMap 由来の部分の表示と、share-alike)。places と addresses は `other` で、元データごとに条件が違う (<https://docs.overturemaps.org/attribution/>)。使った種類ごとに確かめて書く。
