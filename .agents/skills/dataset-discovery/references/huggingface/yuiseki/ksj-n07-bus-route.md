---
kind: dataset
id: yuiseki/ksj-n07-bus-route-jp
description: 国土数値情報のバスルート (N07) の 2022 年版 (第 2.0 版)。バスが通る道筋の線 354,208 本と、その事業者の名前を、全国と都道府県ごとの GeoParquet にしたもの。1 行は 1 本の線で、1 つの系統ではない。首都圏 4 都県だけの版 (yuiseki/ksj-n07-bus-route-greater-tokyo) もある。
url: https://huggingface.co/datasets/yuiseki/ksj-n07-bus-route-jp
card_revision: 5c1d2abce4d0f23eb09926b87bc6d42f800d009c
license: CC BY 4.0 (元は国土数値情報ダウンロードサイトコンテンツ利用規約。政府標準利用規約 2.0 と PDL1.0 に準拠し、CC BY 4.0 と互換)。出典の表示と、加工したことの明記が要る
formats:
- GeoParquet (全国 1 ファイルと都道府県ごと 47 ファイル)
- Shapefile、GeoJSON (元の zip。都道府県ごと 47 と全国 1)
crs: EPSG:6668 (JGD2011 の経度と緯度。GeoParquet のメタデータに PROJJSON で書いてある)
spatial_coverage: 日本全国。路線バス、市町村のコミュニティバス、公営バス。デマンドバスと高速バスは入っていない
temporal_coverage: 2022 年 8 月ごろの資料から作ったもの。資料の時点は事業者によって違う
as_of:
  material: 2022-08 ごろ
  source_last_modified: 2023-06-26
  retrieved: 2026-10-23
contents:
- バスが通る道筋の線
- 線ごとの事業者の名前
- 線の元のファイルの都道府県 (配布元には無い列)
tables:
- name: bus_route
  read: hf://datasets/yuiseki/ksj-n07-bus-route-jp@5c1d2abce4d0f23eb09926b87bc6d42f800d009c/parquet/bus_route.parquet
  grain: 1 本の線 (ある事業者のバスが通る道筋の一部分)。系統 (路線の 1 つの運行の道筋) ではない
  rows: 354208
  id:
  - id
  join_keys:
  - column: pref_code
    type: VARCHAR
    meaning: 2 桁の都道府県コード。線が入っていた元の都道府県のファイル
    unique: false
    joins:
    - jp-admin-2026-09:prefectures.pref_code
  - column: operator
    type: VARCHAR
    meaning: 事業者名の文字列
    unique: false
    joins:
    - ksj-p11-bus-stop-jp:bus_stop.operator
    note: 同じ 2022 年度版のバス停 (P11) の 1,445 の事業者の文字列は、全てここにもある (ksj-p11-bus-stop のカードの実測)
  no_key:
  - name: code5
    note: 市区町村コードは持たない。市区町村の面との空間結合で付ける。線は市区町村の境をまたぐので、長さを配るなら面で切る
  - name: stop
    note: バス停とは ID で結べない。バス停の点は同じ配布元の P11 (yuiseki/ksj-p11-bus-stop-jp) にあり、結ぶなら距離で結ぶ
  columns:
  - name: id
    type: VARCHAR
    meaning: 都道府県コードと、元のファイルの中の順番 (`13-00001` など)。354,208 行で重複が無い (実測)
  - name: pref_code
    type: VARCHAR
    meaning: 都道府県コード (元のファイル)
  - name: pref
    type: VARCHAR
    meaning: 都道府県名 (元のファイル)
  - name: operator
    type: VARCHAR
    meaning: N07_001 事業者名 (配布元のまま)。コミュニティバスなら市町村の名前。空は無い。1,445 種類
  - name: geometry
    type: GEOMETRY('EPSG:6668') (DuckDB 1.5.6 で読んだとき。中身は WKB の LINESTRING)
    meaning: 線。全行が LINESTRING で、空や無効なものは無い (実測)
---

# 国土数値情報 バスルート (ksj-n07-bus-route)

国土交通省の国土数値情報の「バスルートデータ」(N07) の 2022 年版 (第 2.0 版、令和 4 年度)。自治体とバス事業者の資料 (路線図、時刻表、停留所の一覧、一部はウェブサイト) と GTFS-JP から、バスが通る道筋を、地理院地図の背景に合わせて画面で描いたもの (配布元のページの品質の説明による。測量ではない)。系統の名前、時刻、運行の本数は、この版には無い。
分析では、バスが通る道路の範囲、事業者ごとの道筋の広がり、バス停の点 (同じ配布元の P11) と組み合わせた、バスの走る道路からの距離に使う。運行の本数の代わりには使えない。

## どこから読むか

Hugging Face の `yuiseki/ksj-n07-bus-route-jp` (版 5c1d2ab)。

```
hf://datasets/yuiseki/ksj-n07-bus-route-jp@5c1d2abce4d0f23eb09926b87bc6d42f800d009c/parquet/bus_route.parquet          全国 (75 MB)
hf://datasets/yuiseki/ksj-n07-bus-route-jp@5c1d2abce4d0f23eb09926b87bc6d42f800d009c/parquet/prefectures/<code>.parquet  都道府県 (01〜47)
hf://datasets/yuiseki/ksj-n07-bus-route-jp@5c1d2abce4d0f23eb09926b87bc6d42f800d009c/raw/2026-10-23/                    元の zip と MANIFEST.json
```

埼玉県、千葉県、東京都、神奈川県 (11〜14) だけの `yuiseki/ksj-n07-bus-route-greater-tokyo` (版 f5dfc10、58,823 行) もある。全国版の 11〜14 の行と、id、事業者、線の座標まで全て同じ (実測)。全国版から `pref_code in ('11','12','13','14')` で絞れば同じものになる。

- 配布元: <https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N07-v2_0.html>。配布元のファイルの Last-Modified は 2023-06-26。
- 出典の表示 (Hugging Face のカードによる): 出典：「国土数値情報（バスルートデータ）」（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N07-v2_0.html）を加工して作成

## 実測 (2026-10-23、DuckDB 1.5.6)

| 項目 | 値 |
|---|---|
| 行 | 354,208 (都道府県の数の合計と一致。`columns.json` の数とも一致) |
| `id` の重複 | 0 |
| 事業者 | 1,445 種類。NFKC で正規化し空白を除いても、まとまる名前は無かった。188 の事業者は 2 つ以上の都道府県に出る |
| 線の型 | 全て LINESTRING。空と無効は 0 |
| 範囲 | 経度 123.75〜145.81、緯度 24.26〜45.52 |
| 線の長さ (回転楕円体の上) | 合計 171,776 km。1 本の中央値 341 m、90% 点 905 m、99% 点 2.7 km、最長 88.9 km |
| 線の多い事業者 | 神奈川中央交通（株） 5,525、神姫バス（株） 4,167、産交バス（株） 3,569 |

同じ線が重なっている。

- 同じ都道府県、同じ事業者で、座標まで同じ線が 14 組 15 行ある (Hugging Face のカードの「15 行」は、重なって余分な行の数)。
- 座標まで同じで事業者が違う線が 14,783 組 30,719 行ある (1 組に最大 7 事業者)。同じ道を複数の事業者が走るとき、事業者ごとに線がある。
- 東京都 (EPSG:6677 で測った) の線の長さの合計は 5,363 km、線を合わせて重なりを除いた長さは 3,911 km。合計は、重なりの分 (約 27%) だけ長い。

## 気をつけること

- 1 行は系統ではない。1 つの事業者の道筋が、多くの短い線に分かれている。線の数を路線や系統の数として数えない。
- 線の長さを足すと、同じ道を走る事業者の数だけ、同じ道を何度も数える。「バスが通る道路の長さ」なら、線を合わせて (union) 重なりを除いてから測る。「事業者ごとの道筋の長さ」なら、事業者ごとに合わせてから測る。どちらを取ったかを書く。
- 運行の本数、時刻、系統の名前、バスの種類 (路線バス、コミュニティバス、公営) は、この版の線には無い。バスの種類は、同じ配布元のバス停 (P11) にある。
- デマンドバスと高速バスは入っていない (Hugging Face のカードによる)。
- 資料の時点は 2022 年 8 月ごろで、事業者によって違う。その後に変わった道筋は入っていない。
- `pref_code` は、線が入っていた元の都道府県のファイルで、線の位置から決めたものではない。線の中点を `jp-admin-2026-09` の都道府県の面に入れると (2026-10-23 実測)、164 本は別の都道府県の面に入り (佐賀県のファイルの西肥自動車の 29 本が長崎県、東京都のファイルの国際興業と西武バスの 23 本が埼玉県、埼玉県のファイルの所沢市の 20 本が東京都、など)、241 本はどの面にも入らず (海岸と島の面の外とみられる)、91 本は 2 つの面に入った (県の境の面の重なり)。都道府県で集計するなら、`pref_code` ではなく面で切ってから測る。
- 配布元の全国の zip は、都道府県の zip を合わせたものと違う (353,453 本。境で線を切る場所が違うとみられる。Hugging Face のカードによる)。Parquet は都道府県の zip から作ってある。
- 測地系は JGD2011 (EPSG:6668)。`jp-admin-2026-09` の面は JGD2000 (EPSG:4612) なので、DuckDB の空間関数は CRS が違うと止まる。2 つの差は、2011 年の地震の地殻変動を直した東日本の一部で最大数 m、ほかではほぼ 0 (一般の知識で、ここでは測っていない)。境の判定に効く距離でなければ `ST_SetCRS` で揃えてよいが、揃えたことを書く。
- 2011 年版 (第 1.0 版) は非商用の条件なので入っていない。2011 年版にあった系統の名前と本数は、この版には無い。

## 読み方の例

```sql
-- DuckDB (spatial)。東京都の、バスが通る道の長さ (重なりを除く)
install spatial; load spatial;
select round(ST_Length(ST_Union_Agg(
         ST_Transform(geometry, 'EPSG:6668', 'EPSG:6677', always_xy := true))) / 1000) as km
from 'hf://datasets/yuiseki/ksj-n07-bus-route-jp@5c1d2abce4d0f23eb09926b87bc6d42f800d009c/parquet/prefectures/13.parquet';
-- 3911 (島しょ部を含む)
```
