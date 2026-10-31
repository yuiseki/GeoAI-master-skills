---
kind: dataset
id: yuiseki/mlit-kansui-flood-prone-points-jp-2026-09
description: 国土交通省の8つの地方整備局の「道路防災情報Webマップ」が載せる冠水想定箇所 (周りより低く、局地的な大雨で冠水しうる道路の箇所。多くはアンダーパス) 4,525 点を、45 都府県の KML から読んだ GeoParquet。名前と座標は KML のまま。箇所ごとの説明表 (箇所表) の PDF への URL を持ち、PDF から読んだ表は別のデータセット (mlit-kansui-flood-prone-points-pdf-jp-2026-09) にある。
url: https://huggingface.co/datasets/yuiseki/mlit-kansui-flood-prone-points-jp-2026-09
license: PDL1.0 (HF の表示は other / pdl-1.0)。根拠は各地方整備局のサイト全体の利用規約で、Webマップや KML そのものに権利の表記は無い (配布者が 2026-10-30 に確認)。規約が KML に及ぶかは利用者が判断する。局ごとの出典の表示と、加工したことの記載が要る
formats:
- GeoParquet (parquet/kansui_points.parquet)
- KML (配布元のまま、raw/20261030/)
crs: EPSG:4326 (経度と緯度。geometry 列の型は GEOMETRY('EPSG:4326'))
spatial_coverage: 北海道と沖縄県を除く 45 都府県。関東 903、北陸 751、近畿 717、中部 691、九州 568、東北 503、中国 273、四国 119 点
temporal_coverage: 2026-10-30 取得。KML の Last-Modified は 2020-09-04〜2024-06-26 で県ごとに違う。局のページが書く冠水想定箇所の更新日は 平成25年9月〜令和8年3月。点ごとの日付は無い
as_of:
  retrieved: 2026-10-30
  huggingface_revision: d4e2e1f6a3278a9956044094acd852a73c5283f2
contents:
- 冠水想定箇所の点、名前 (KML の Placemark 名)、都府県、地方整備局
- 箇所表 PDF の URL と、そのファイル名の stem (pdf_key)
- 元の KML の URL と Last-Modified
tables:
- name: kansui_points
  read: hf://datasets/yuiseki/mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f6a3278a9956044094acd852a73c5283f2/parquet/kansui_points.parquet
  grain: 1 つの冠水想定箇所 (KML の 1 つの Placemark)
  rows: 4525
  id:
  - fid
  join_keys:
  - column: pdf_key
    type: VARCHAR
    meaning: 箇所表 PDF のファイル名の stem。PDF のデータセットの pdf_records.pdf_key と結ぶ
    unique: false
    joins:
    - yuiseki/mlit-kansui-flood-prone-points-pdf-jp-2026-09:pdf_records.pdf_key
  - column: fid
    type: BIGINT
    meaning: 行の番号 (1〜4,525)
    unique: true
    joins:
    - yuiseki/mlit-kansui-flood-prone-points-pdf-jp-2026-09:point_pdf.fid
  no_key:
  - name: name
    note: 同じ都府県の中で名前が重なる行が 182 ある。座標が同じ行は 11 ある。名前で結ばない
  - name: mlit-underpass の id
    note: 国のアンダーパス一覧 (mlit-underpass) と共通の ID は無い。距離で対応づける (下の実測)
  columns:
  - name: fid
    type: BIGINT
    meaning: 行の番号 (1〜4,525、重複なし)
  - name: layer
    type: VARCHAR
    meaning: KML のファイル名 (`<NN>_<県のローマ字>_kansui_point` の形)
  - name: pref_code
    type: VARCHAR
    meaning: KML のファイル名の番号
  - name: pref_roma
    type: VARCHAR
    meaning: 県のローマ字 (ファイル名から)
  - name: pref
    type: VARCHAR
    meaning: 都府県名 (KML の県。点が県の面の外にある行が 10 ある。下の注意)
  - name: bureau
    type: VARCHAR
    meaning: 地方整備局の略号 (thr、ktr、hrr、cbr、kkr、cgr、skr、qsr)
  - name: bureau_ja
    type: VARCHAR
    meaning: 地方整備局の名前
  - name: name
    type: VARCHAR
    meaning: KML の Placemark の名前 (配布元のまま。管理番号の形が多い)
  - name: lon
    type: DOUBLE
    meaning: 経度 (KML のまま。小数 4〜9 桁、4 桁に丸められた点は約 10 m の粒度)
  - name: lat
    type: DOUBLE
    meaning: 緯度 (KML のまま)
  - name: pdf_href
    type: VARCHAR
    meaning: KML に書かれた PDF へのリンク
  - name: pdf_url
    type: VARCHAR
    meaning: pdf_href を https の絶対 URL にしたもの
    missing: NULL が 4 行 (全て岩手県。箇所表へのリンクが無い)
  - name: pdf_key
    type: VARCHAR
    meaning: PDF のファイル名の stem。4,429 種類で、92 行は他の行と同じ PDF を指す (秋田県は 1 つの PDF を共有、山形県にも共有あり)
  - name: style_url
    type: VARCHAR
    meaning: KML のスタイルの参照
  - name: source_last_modified
    type: VARCHAR
    meaning: KML の HTTP の Last-Modified (文字列のまま)
  - name: source_url
    type: VARCHAR
    meaning: KML の URL (45 種類)
  - name: geometry
    type: GEOMETRY('EPSG:4326')
    meaning: lon と lat の点
  - name: bbox
    type: STRUCT(xmin DOUBLE, ymin DOUBLE, xmax DOUBLE, ymax DOUBLE)
    meaning: GeoParquet 1.1 の bbox 列
---

# 地方整備局の冠水想定箇所 45 都府県 (mlit-kansui-flood-prone-points-jp-2026-09)

国土交通省の地方整備局が「道路防災情報Webマップ」で公開する冠水想定箇所の点。Webマップが読み込む KML (Webマップの `kml/` の下の `<NN>_<県>_kansui_point.kml`、URL は `source_url` 列) を 2026-10-30 に取り、Placemark を GeoParquet にした。値の訂正はしていない。配布元が KML の中でコメントアウトした取り下げの 2 点 (京都府-02-020、大阪府-02-030) は行に無い。

冠水想定箇所は「冠水が起きた箇所」ではなく、道路管理者が冠水のおそれがあるとして示す箇所。国のアンダーパス一覧 ([mlit-underpass](mlit-underpass.md)) とほぼ重なる (下の実測)。どちらも冠水のおそれのある箇所に絞った一覧と見られ (未確認)、同じ選び方の 2 つの表れなので、互いを独立した確かめに使えない。一覧の中だけで冠水の起きやすさを比べると、選ばれなかった箇所との違いは見えない。箇所表 PDF の表 (住所、管理者、備考の冠水実績や関連設備) は [mlit-kansui-flood-prone-points-pdf-jp-2026-09](mlit-kansui-flood-prone-points-pdf-jp-2026-09.md) にあり、`pdf_key` か `fid` で結ぶ。

## 気をつけること

- 北海道と沖縄県は無い:
  同じ形の KML が見つからなかった。国のアンダーパス一覧の北海道 47 か所と沖縄県 2 か所には、対応する点が無い。
- 県の外の点:
  10 点が、書かれた県の面 (jp-admin-2026-09) の外にある。7 点は 100 m より外 (宮城県の 3 点が約 35 km、栃木県の 4 点が 4〜6 km)。配布元のまま残してあり、一覧は HF の `docs/prefecture_outliers.tsv`。
- 箇所表の PDF は点ごとに一意ではない:
  92 行が他の行と同じ PDF を指す。PDF の表の値をそのまま点に付けられるのは、PDF のデータセットの `point_pdf.pdf_match` が `pdf_unique` の 3,997 点。
- 国のアンダーパス一覧との関係:
  どちらにも共通の ID は無い。距離で結ぶと、ほぼ同じ箇所の集合になる (下の表)。地方整備局ごとに載せる範囲 (国道だけか、県や市町村の道路も含むか) が同じかは未確認。

## 補足の実測 (2026-10-31、DuckDB 1.5.5 以上、固定した版から)

| 項目 | 値 |
|---|---|
| 行 | 4,525 点、45 都府県、fid の重複なし。pdf_key は 4,429 種類 |
| 重複 | 同じ都府県で名前が重なる行 182、座標が重なる行 11 (README と一致) |
| 国のアンダーパス (mlit-underpass@4d00072、3,841 か所) との距離 | KML のある 45 都府県の 3,792 か所のうち、最寄りの冠水想定箇所が 10 m 以内 3,118、30 m 以内 3,319 (87.5%)、100 m 以内 3,398、300 m 以内 3,466 |
| 逆向き | 冠水想定箇所 4,525 点のうち、30 m 以内に国のアンダーパスがあるのは 3,320 点 |

距離は大円距離 (`ST_Distance_Sphere`、`geometry_always_xy = true`)。スクリプトは `evals/curriculum/dry-runs/underpass-pilots/kansui_labels.py`。

## 出典の表示

局ごとに「出典：<局>ホームページ（Webマップの URL）」と、「「道路防災情報Webマップ 冠水想定箇所」（<局>）（URL）を加工して作成」を書く。8 局の文面と URL は HF の README にある。国が作成したかのような態様で公表してはいけない。
