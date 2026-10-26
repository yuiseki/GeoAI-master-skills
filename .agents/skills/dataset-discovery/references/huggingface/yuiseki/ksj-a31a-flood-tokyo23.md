---
kind: dataset
id: yuiseki/ksj-a31a-flood-tokyo23
description: 国土数値情報の洪水浸水想定区域 (河川単位、A31a) の令和7年度版から、東京 23 区にかかる面 227,651 個を取り出した GeoParquet。計画規模と想定最大規模の浸水深、浸水継続時間、家屋倒壊等氾濫想定区域 (氾濫流、河岸侵食) の 5 種類。面は河川ごとで、同じ場所に複数の河川の面が重なる。
url: https://huggingface.co/datasets/yuiseki/ksj-a31a-flood-tokyo23
license: CC BY 4.0 (国土数値情報ダウンロードサイトが令和7年度版を CC_BY_4.0 と表示し、サイトの利用規約と「都道府県毎に定められた利用条件」に従うよう求めている。後者の中身は見つかっていない)。出典の表示と加工の明記が要る
formats:
- GeoParquet (全部の 1 ファイルと、種類ごとの 5 ファイル)
- Shapefile の zip 5 (配布元のまま、raw/2026-10-26/)
crs: EPSG:6668 (JGD2011 の経緯度。GeoParquet のメタデータに PROJJSON で書いてある)
spatial_coverage: 東京 23 区にかかる面。面は切っていないので 23 区の外にはみ出す (経度 139.45〜139.92、緯度 35.54〜35.92)
temporal_coverage: 令和7年度版 (配布元は 2026 年 5 月と 10 月に更新、ファイルの Last-Modified は 2026-10-09)。想定は河川管理者の各図の時点による
as_of:
  source_last_modified: 2026-10-09
  retrieved: 2026-10-26
  huggingface_revision: 5b2259273128d0b79b491eb758abe0db67c4feac
contents:
- 河川ごと、種類ごと、ランクごとの浸水想定の面
- 河川のコードと名前、データの管理者 (東京都、埼玉県、関東地方整備局)
tables:
- name: flood_area
  read: hf://datasets/yuiseki/ksj-a31a-flood-tokyo23@5b2259273128d0b79b491eb758abe0db67c4feac/parquet/flood_area.parquet
  grain: 1 つの河川の 1 つの種類の 1 つのランクの面 (の一部)。場所ごとの値ではない
  rows: 227651
  id:
  - id
  no_key:
  - name: code5
    note: 市区町村コードは無い。面は区の境で切っていない。区ごとに測るなら jp-admin-2026-09 の面で切る (EPSG:4612 との差に注意、本文)
  - name: depth_per_place
    note: 場所ごとの最大の浸水深は無い。河川ごとの面を重ねて自分で作る (配布元の A31b はそれをメッシュで作ったもので、ここには無い)
  columns:
  - name: id
    type: VARCHAR
    meaning: 地域、グループ、種類、河川コード、元のファイルの中の順番 (`13-10-20-8303040044-000123` など)。重複なし
  - name: category
    type: VARCHAR
    meaning: planned 計画規模、maximum 想定最大規模、duration 浸水継続時間、collapse_flow 家屋倒壊等氾濫想定区域 (氾濫流)、collapse_erosion 同 (河岸侵食)
  - name: river_code
    type: VARCHAR
    meaning: 河川コード (A31a_x01)。22 種類
  - name: river_name
    type: VARCHAR
    meaning: 河川名 (A31a_x02)
  - name: manager
    type: VARCHAR
    meaning: データの管理者 (A31a_x04)。東京都、埼玉県、関東地方整備局
  - name: class_code
    type: TINYINT
    meaning: ランク (A31a_x05)。planned と maximum は浸水深 1〜6、duration は継続時間 1〜7、家屋倒壊は 1 氾濫流、2 河岸侵食
  - name: river_group
    type: VARCHAR
    meaning: 10 洪水予報河川・水位周知河川、20 その他の河川
  - name: source_zip
    type: VARCHAR
    meaning: 元の zip
  - name: geometry
    type: GEOMETRY('EPSG:6668')
    meaning: 面 (全て POLYGON)。GEOS で無効な面を直さずに残している
---

# 国土数値情報 洪水浸水想定区域 東京23区 (ksj-a31a-flood-tokyo23)

国土交通省の国土数値情報「洪水浸水想定区域データ（河川単位）」(A31a) の令和7年度版 (<https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A31a-2025.html>) から、東京 23 区の面 (N03 の 2026-01-01 版) と交わる面を取り出したもの。配布元は管理者ごとに zip を分けているので、東京都 (13)、埼玉県 (11)、関東地方整備局 (83) の 5 つの zip を読んだ。08、12、14、19、22 の zip も全て読み、23 区にかかる面が無いことを確かめてある (README)。
分析では、区や施設、人口のメッシュが浸水の想定にどれだけかかるかに使う。全国版の前の試しの版。

## ランク

| class_code | 浸水深 (planned、maximum) | 継続時間 (duration) |
|---|---|---|
| 1 | 0〜0.5 m 未満 | 12 時間未満 |
| 2 | 0.5〜3.0 m 未満 | 12〜24 時間未満 |
| 3 | 3.0〜5.0 m 未満 | 24〜72 時間未満 |
| 4 | 5.0〜10.0 m 未満 | 72〜168 時間未満 |
| 5 | 10.0〜20.0 m 未満 | 168〜336 時間未満 |
| 6 | 20.0 m 以上 | 336〜672 時間未満 |
| 7 | | 672 時間以上 |

## 実測 (2026-10-26、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 行 | 227,651。`id` の重複 0 |
| 種類 | maximum 136,671、planned 50,124、duration 40,374、collapse_flow 301、collapse_erosion 181 (README と一致) |
| 無効な面 (ST_IsValid) | maximum 3,915、planned 1,316、duration 779、collapse_flow 18、collapse_erosion 4 (README と一致) |
| 河川 | コードで 22、名前で 22。管理者 3 |
| 範囲 | 経度 139.451〜139.918、緯度 35.538〜35.917 |
| 重なりの例 | 江戸川区役所のあたり (139.8683, 35.7067。jp-admin-2026-09 では江戸川区の面) には、maximum で荒川 (関東地方整備局) のランク 3 (3〜5 m) と中川 (東京都) のランク 1 (0.5 m 未満) の 2 つの面が重なる。duration は荒川のランク 6 (336〜672 時間) |

## 気をつけること

- 面は河川ごと。同じ場所に、複数の河川の、それぞれのランクの面がある。場所の浸水深は、その場所にかかる面のランクの最大を取るなど、自分で決めて作り、決め方を書く。面の面積を足して浸水の面積にしない。
- 種類も重なる。planned と maximum は別の想定 (降雨の規模が違う) で、同じ場所に両方ある。どちらを使ったかを書く。
- 無効な面が残っている。面積や交差を測る前に `ST_MakeValid` するか、無効な面をどう扱ったかを書く。
- 面は 23 区で切っていないので、区の外まで伸びる。23 区の中で測るなら、区の面で切る。jp-admin-2026-09 の面は EPSG:4612 (JGD2000) なので、DuckDB の空間関数は CRS が違うと止まる。`ST_SetCRS` で揃えたなら、そう書く。
- 想定は、支川の氾濫、想定を超える雨、高潮、内水を含まない。想定の外でも浸水しうるし、深さは想定を超えうる (配布元)。東京都の「浸水予想区域図」(内水を含む) とは別物。
- 浅川と大栗川 (多摩川の支川) の面が、多摩川の下流の平地 (北緯 35.54 度あたり) にまで広がっている。配布元のまま。理由は確かめていない。
- 位置の精度は 25 m (配布元)。ランクの色分けは、管理者が公表している地図と違うことがある。
- 管理者がデータを出していない河川は入っていない。

## 出典の表示

> 出典：「国土数値情報（洪水浸水想定区域データ（河川単位））」（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A31a-2025.html）を加工して作成
