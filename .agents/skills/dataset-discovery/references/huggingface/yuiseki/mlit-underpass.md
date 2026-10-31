---
kind: dataset
id: yuiseki/mlit-underpass
description: 国土交通省 道路局の「全国のアンダーパス箇所マップ」の点。前後の区間より大きく低くなる道路の区間 (アンダーパス部) 3,841 か所を、全国と都道府県ごとの GeoParquet にしたもの。1 行が 1 つの箇所。
url: https://huggingface.co/datasets/yuiseki/mlit-underpass
card_revision: 4d00072aa88696cfa7026c4cef7d600bc96f9f13
license: CC BY 4.0 (元は国土交通省のサイトの利用規約による PDL1.0)。出典の表示と、加工したことの明記が要る
formats:
- GeoParquet 1.1 (全国 1 ファイルと都道府県ごと 47 ファイル)
- GeoJSON (元の 10 ブロック)
crs: OGC:CRS84 (経度と緯度。ファイルは CRS を書かず、GeoParquet の既定の CRS84 になる。配布元は CRS を書いていないが、地図はこの順で描いている)
spatial_coverage: 日本全国。国と地方公共団体が管理する道路だけで、高速道路会社の道路は入っていない
temporal_coverage: 地図の時点は令和 7 年 3 月 31 日 (2025-03-31)。点ごとの日付は無い
as_of:
  map_date: 2025-03-31
  retrieved: 2026-10-17
contents:
- アンダーパス部の点、名前、路線名、道路の管理者
- 点から判定した都道府県 (配布元には無い列)
tables:
- name: underpass
  read: hf://datasets/yuiseki/mlit-underpass@4d00072aa88696cfa7026c4cef7d600bc96f9f13/parquet/national.parquet
  grain: 1 つのアンダーパスの箇所 (配布元の地図の 1 つの点)
  rows: 3841
  id:
  - id
  join_keys:
  - column: pref_code
    type: VARCHAR
    meaning: 2 桁の都道府県コード。点を jp-admin-2026-09 の都道府県の面に入れて決めたもの
    unique: false
    joins:
    - jp-admin-2026-09:prefectures.pref_code
  no_key:
  - name: code5
    note: 市区町村コードは持たない。jp-admin-2026-09 の市区町村の面との空間結合で付ける。全ての点がどれかの面に入る。政令指定都市の 488 点は、市の面と区の面の 2 つに入る
  columns:
  - name: id
    type: VARCHAR
    meaning: ブロックのコードと、そのブロックのファイルの中の順番 (`83knt-0001` など)。3,841 行で重複が無い (実測)
  - name: block
    type: VARCHAR
    meaning: 配布元の地図のブロック (北海道地方〜沖縄地方の 10)
  - name: name
    type: VARCHAR
    meaning: 箇所の名前 (配布元のまま)
  - name: route
    type: VARCHAR
    meaning: 路線名 (配布元のまま。「４号」「（一）新居浜港線」など書式はまちまち)
  - name: manager
    type: VARCHAR
    meaning: 道路の管理者 (地方整備局、都道府県、市区町村)
  - name: pref_code
    type: VARCHAR
    meaning: 都道府県コード (点から判定)
  - name: pref
    type: VARCHAR
    meaning: 都道府県名 (点から判定)
  - name: pref_dist_deg
    type: DOUBLE
    meaning: 点が都道府県の面の中なら 0、外なら最寄りの面までの度。全行 0
  - name: lon
    type: DOUBLE
    meaning: 経度 (配布元のまま)
  - name: lat
    type: DOUBLE
    meaning: 緯度 (配布元のまま)
  - name: geometry
    type: GEOMETRY('OGC:CRS84') (DuckDB 1.5.6 で読んだとき。中身は WKB)
    meaning: lon と lat と同じ点。全行で一致した (実測)
---

# 全国のアンダーパス箇所マップ (mlit-underpass)

国土交通省 道路局が、道路の災害の情報のページ (`road/saigai/`) で公開している、アンダーパス部の点。アンダーパス部は「主に市街地で道路や鉄道と立体交差し、前後の区間より急に低くなる区間」(都道府県別の表の注記、カードによる)。一覧に載せる箇所の選び方は、地図のページ (2026-10-31 に読んだ) に書かれていない。全てのアンダーパスの一覧ではなく、道路管理者が冠水のおそれのある箇所に絞ったものと見るのが安全 (依頼者の見立て、未確認)。東京 23 区では、凍結の OSM (osm-tokyo23-src-2026-08@38f7a5f) の `tunnel` が yes か covered、または `layer<0` の道路から作った候補 252 か所に対し、この一覧は 99 か所で、候補の約 7 割は一覧の点から 100 m 以内に無い (2026-10-17 実測)。タグの無い鉄道のガード下は候補にも入らないので、一覧に無いアンダーパスはもっと多い。この一覧を「全てのアンダーパス」の母集団にすると、選ばれた側だけを比べることになる。点ごとの冠水の起きやすさ、深さ、通行止めの基準は無い。
分析では、浸水の想定区域や降雨との重ね合わせ、道路網の上での迂回、避難の経路の上の障害の数え上げに使う。

## どこから読むか

Hugging Face の `yuiseki/mlit-underpass`。

```
hf://datasets/yuiseki/mlit-underpass/parquet/national.parquet          全国 3,841 点 (1 row group)
hf://datasets/yuiseki/mlit-underpass/parquet/prefectures/<code>.parquet 都道府県ごと (47 ファイル)
hf://datasets/yuiseki/mlit-underpass/parquet/columns.json               都道府県ごとの件数
hf://datasets/yuiseki/mlit-underpass/raw/2026-10-17/                    元の 10 ブロックの GeoJSON と MANIFEST.json (sha256)
```

- カード: <https://huggingface.co/datasets/yuiseki/mlit-underpass>
- 取得と変換のコード: <https://github.com/yuiseki/mlit-underpass>
- 配布元: <https://www.mlit.go.jp/road/saigai/underpass/map/map.html> (地図)、<https://www.mlit.go.jp/road/road_fr4_000208.html> (件数と時点)、<https://www.mlit.go.jp/road/content/002022076.pdf> (都道府県別の表)。
- 出典の表示: 出典：「全国のアンダーパス箇所マップ」（国土交通省）（https://www.mlit.go.jp/road/saigai/underpass/map/map.html）をもとに作成。変えたなら「加工して作成」と書き、国が作ったように見せない。

## DuckDB で読む

版 4d00072 から、DuckDB 1.5.6 でそのまま読める。`geometry` は `GEOMETRY('OGC:CRS84')` の列になる (2026-10-17 に全国と都道府県ごとのファイルで実測)。

```sql
select id, name, route, manager, pref_code, geometry
from 'hf://datasets/yuiseki/mlit-underpass/parquet/national.parquet';
```

前の版 e16afd6 は、`geo` メタデータの `crs` が文字列 `"EPSG:4326"` で、GeoParquet 1.1 の仕様 (PROJJSON のオブジェクトか、省略して CRS84) に合わず、DuckDB 1.5.6 は `Geoparquet column 'geometry' has invalid CRS` で止まった。版 4d00072 では `crs` を省いただけで、`geometry` を含む全ての列の値は前の版と同じ (pyarrow で比べた)。前の版を読むなら、`set enable_geoparquet_conversion = false` にして `ST_Point(lon, lat)` で点を作る。

## 件数

2026-10-17 に実測。

| 項目 | 値 |
|---|---|
| 行 | 3,841 (都道府県ごとのファイルの合計も 3,841、`id` の重複なし) |
| ブロック | 関東地方 966、近畿地方 765、中部地方 543、北陸地方 440、東北地方 393、九州地方 289、中国地方 251、四国地方 145、北海道地方 47、沖縄地方 2 |
| 都道府県 | 47 全てに 1 点以上。最多は埼玉県 270、新潟県 231、兵庫県 188。東京都 153。最少は沖縄県 2 |
| 欠け | `name`、`route`、`manager` に空の行なし |
| 範囲 | 経度 127.66〜144.39、緯度 26.20〜44.10 |
| 管理者 | 上位は東京都 76、大阪市 61、新潟市 60、関東地方整備局 59、京都市 42。名前で分けると、地方整備局などの国が 136、都道府県が 760、残り (ほぼ市区町村) が 2,945 |

カードによると、都道府県ごとの件数と合計は、国土交通省の都道府県別の表と全て一致する (この表は確かめていない)。

## 気をつけること

- 同じ名前、路線、管理者の行が 35 組 72 行ある (37 行が別の行と重なる)。座標まで同じなのは 5 組。ほとんどは同じ名前の別の箇所で、配布元のまま全て残してある。逆に、座標が同じ 10 組 20 行には、名前の違う組もある (仙台市の「西中田一丁目ガード」と「長町一丁目ガード」など)。箇所を数えるなら、どちらで 1 つとみなすかを決めて書く。
- 高速道路会社の道路は入っていない。全てのアンダーパスの一覧ではない。
- 地図の時点は 2025-03-31 で、ページの更新 (2026-09-17) より古い (カードによる)。
- 位置の精度と測地系は書かれていない。点は区間の代表で、低い区間の範囲 (長さ、最も低い点) は無い。道路の線に重ねるなら、点から近い線を選ぶ距離を決めて、選べなかった点を数える。
- `88skk-0101` (横水アンダー) は愛媛県にあるが、管理者は高知県と書かれている。配布元のまま (実測)。
- `pref_code` は点から判定したもので、配布元の列ではない。管理者の都道府県とは限らない。

## ほかのデータとの結合

- `pref_code` で `jp-admin-2026-09` の都道府県と結べる。市区町村は、市区町村の面に点を入れて付ける。全 3,841 点がどれかの面に入った。政令指定都市の 488 点は、親の市の面と区の面の両方に入るので、`ward is null` の行か区の行のどちらかに絞ってから数える。
- 浸水の想定区域 (国土数値情報、`mlit-nlftp/` の目録) の面に点を入れれば、想定区域の中のアンダーパスを数えられる。この一覧そのものは、冠水の起きやすさを表さない。
- 地方整備局の冠水想定箇所 ([mlit-kansui-flood-prone-points-jp-2026-09](mlit-kansui-flood-prone-points-jp-2026-09.md)) とは共通の ID が無く、距離で結ぶ。北海道と沖縄県を除く 3,792 か所のうち 3,319 か所 (87.5%) が 30 m 以内にある (2026-10-31 実測)。指定されているかどうかは、冠水の起きやすさのラベルとしては弱い。箇所表の備考の冠水実績は [PDF の表](mlit-kansui-flood-prone-points-pdf-jp-2026-09.md) にあり、12 府県にしか書かれていない。
- 道路網の上で迂回の距離を測るなら、OpenStreetMap の道路 (`osm-japan-src-2026-08`) に点を寄せる。OSM の道路は EPSG:3857 なので、距離はメートルの投影で測る。
