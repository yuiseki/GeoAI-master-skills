---
kind: dataset
id: yuiseki/mlit-kansui-flood-prone-points-pdf-jp-2026-09
description: 地方整備局の冠水想定箇所の KML の点が指す箇所表 PDF 4,410 件から、表のセルの文字を pdfplumber で読んだ Parquet (管理番号、箇所名、アンダーパス名、住所、管理者、警察と消防、備考)。備考と北陸の様式の追加の欄に、冠水実績や関連設備 (排水ポンプ、水位センサー、警報・情報板) が書かれていることがある。PDF そのものは含まない。読み取りには不確かさがある。
url: https://huggingface.co/datasets/yuiseki/mlit-kansui-flood-prone-points-pdf-jp-2026-09
license: PDL1.0 (HF の表示は other / pdl-1.0)。根拠は各地方整備局のサイト全体の利用規約。PDF には地理院地図と現地の写真が入るので、PDF は再配布していない。局ごとの出典の表示と、加工したことの記載が要る
formats:
- Parquet (parquet/pdf_records.parquet, parquet/point_pdf.parquet)
- JSON (raw/*/PDF_MANIFEST.json。PDF ごとの URL、HTTP の状態、大きさ、Last-Modified、sha256)
crs: null
spatial_coverage: 点のデータセットと同じ 45 都府県 (北海道と沖縄県を除く)
temporal_coverage: PDF は 2026-10-30 と 2026-10-31 に取得。備考の冠水実績の年は PDF ごとにまちまち (平成16年度以降など)
as_of:
  retrieved: 2026-10-31
  huggingface_revision: 34e24d0c94dbeec34a45dba934675ec1a1cf0a97
contents:
- PDF ごとの表の文字 (1 PDF 1 行。読めなかったセルは NULL)
- 点と PDF の対応と、その確かさ (pdf_match)
tables:
- name: pdf_records
  read: hf://datasets/yuiseki/mlit-kansui-flood-prone-points-pdf-jp-2026-09@34e24d0c94dbeec34a45dba934675ec1a1cf0a97/parquet/pdf_records.parquet
  grain: 1 つの箇所表 PDF (読めた PDF は 1 件の記録、様式を読めなかった 403 件は record_no 0 で属性が全て NULL)
  rows: 4410
  id:
  - pdf_key
  join_keys:
  - column: pdf_key
    type: VARCHAR
    meaning: PDF のファイル名の stem
    unique: true
    joins:
    - point_pdf.pdf_key
    - yuiseki/mlit-kansui-flood-prone-points-jp-2026-09:kansui_points.pdf_key
  no_key:
  - name: mgmt_no
    note: 管理番号は読み取りの崩れ (ハイフンの欠け、2 行目の連結) を含みうる。結合には pdf_key を使う
  columns:
  - name: pdf_name
    type: VARCHAR
    meaning: 手元のファイル名 (`<局>__<stem>.pdf`)
  - name: pdf_url
    type: VARCHAR
    meaning: 局のサイトの PDF の URL
  - name: pdf_key
    type: VARCHAR
    meaning: PDF のファイル名の stem (一意)
  - name: pdf_sha256
    type: VARCHAR
    meaning: 取得した PDF の sha256 (局が差し替えると変わる)
  - name: pdf_pages
    type: BIGINT
    meaning: PDF のページ数
  - name: layout
    type: VARCHAR
    meaning: 様式 (`A` 説明表・箇所表・様式 3,369 件、`B` 北陸の道路冠水(危険)想定箇所の様式 638 件 [石川、富山、新潟]、`unknown` 403 件)
  - name: record_no
    type: BIGINT
    meaning: PDF の中の記録の番号 (読めた 4,007 件は 1、unknown は 0)
  - name: parse_status
    type: VARCHAR
    meaning: 読み取りの状態 (`ok` 3,953、`ambiguous` 54 [必須のセルが空か読めない、parse_note を見る]、`layout_unknown` 403)
  - name: mgmt_no
    type: VARCHAR
    meaning: 管理番号・整理番号 (読んだまま)
  - name: place_name
    type: VARCHAR
    meaning: 箇所名称 (様式 A。路線名と箇所が一緒に書かれていることが多い)
    missing: 様式 B は全て NULL。ふりがなの混入で伏せた記録も NULL
  - name: road_name
    type: VARCHAR
    meaning: 道路名 (様式 B だけ。様式 A では全て NULL で、路線は place_name に入る)
  - name: underpass_name
    type: VARCHAR
    meaning: アンダーパス等の名称・施設名
  - name: road_kind
    type: VARCHAR
    meaning: 道路の種別 (国道、県道、市道、町道など。様式 A だけ)
  - name: pref_name
    type: VARCHAR
    meaning: 都府県名 (表に書かれたもの)
  - name: municipality
    type: VARCHAR
    meaning: 市町村 (様式 A だけ。3,340 件)
  - name: aza_chome
    type: VARCHAR
    meaning: 字・丁目
  - name: banchi
    type: VARCHAR
    meaning: 番地
  - name: sakimei
    type: VARCHAR
    meaning: 地先名
  - name: manager_name
    type: VARCHAR
    meaning: 道路の管理者の名前
  - name: manager_tel
    type: VARCHAR
    meaning: 管理者の電話番号
  - name: manager_tel_text
    type: VARCHAR
    meaning: 様式 B の管理者の残りのセル (読んだまま)
  - name: police_name
    type: VARCHAR
    meaning: 警察署の名前 (様式 A)
  - name: police_tel
    type: VARCHAR
    meaning: 警察署の電話番号 (様式 A)
  - name: police_text
    type: VARCHAR
    meaning: 警察署の名前と電話番号を一緒に書いたセル (様式 B)
  - name: fire_name
    type: VARCHAR
    meaning: 消防署の名前 (様式 A)
  - name: fire_tel
    type: VARCHAR
    meaning: 消防署の電話番号 (様式 A)
  - name: fire_text
    type: VARCHAR
    meaning: 消防署の名前と電話番号のセル (様式 B)
  - name: remarks
    type: VARCHAR
    meaning: 備考 (様式 A だけ、968 件に値がある)。関連設備、冠水実績の有無や年、交差物件などが自由な書き方で入る
  - name: extra_cells
    type: VARCHAR
    meaning: 様式ごとの追加の欄の JSON。北陸の 464 件に 冠水範囲、冠水原因、1m以上の冠水の有無、排水ポンプの有無、注意喚起方法、情報入手方法、通行止方法、看板に記載する連絡先、その他 がある
  - name: parse_note
    type: VARCHAR
    meaning: 読み取りの補足
  - name: bureau
    type: VARCHAR
    meaning: 地方整備局の略号
  - name: name_cells
    type: VARCHAR
    meaning: 名前のセルの扱い (`as_read` 3,941、`withheld_furigana_in_source` 469。後者は place_name、underpass_name、road_kind を NULL にした)
- name: point_pdf
  read: hf://datasets/yuiseki/mlit-kansui-flood-prone-points-pdf-jp-2026-09@34e24d0c94dbeec34a45dba934675ec1a1cf0a97/parquet/point_pdf.parquet
  grain: 点のデータセットの 1 点
  rows: 4525
  id:
  - fid
  join_keys:
  - column: fid
    type: BIGINT
    meaning: 点のデータセットの fid
    unique: true
    joins:
    - yuiseki/mlit-kansui-flood-prone-points-jp-2026-09:kansui_points.fid
  - column: pdf_key
    type: VARCHAR
    meaning: PDF のファイル名の stem
    unique: false
    joins:
    - pdf_records.pdf_key
  columns:
  - name: fid
    type: BIGINT
    meaning: 点の番号
  - name: layer
    type: VARCHAR
    meaning: KML のファイル名
  - name: pref
    type: VARCHAR
    meaning: 都府県名
  - name: name
    type: VARCHAR
    meaning: KML の名前
  - name: pdf_name
    type: VARCHAR
    meaning: 手元の PDF のファイル名
  - name: pdf_url
    type: VARCHAR
    meaning: PDF の URL
  - name: pdf_key
    type: VARCHAR
    meaning: PDF のファイル名の stem
  - name: pdf_match
    type: VARCHAR
    meaning: 点と表の対応 (`pdf_unique` 3,997 [この点だけが指し、記録が 1 件]、`pdf_shared` 504 [どの記録がどの点かは書かれていない]、`pdf_missing` 20 [HTTP 404]、`no_pdf` 4)
  - name: pdf_key_consistent
    type: BOOLEAN
    meaning: ファイル名の番号と管理番号の番号が合うか (確認用。記録のある 119 点で false、配布元のまま)
---

# 冠水想定箇所の箇所表 PDF から読んだ表 (mlit-kansui-flood-prone-points-pdf-jp-2026-09)

[mlit-kansui-flood-prone-points-jp-2026-09](mlit-kansui-flood-prone-points-jp-2026-09.md) の点が指す箇所表 PDF を取得し、表のセルの文字を pdfplumber で読んだもの。推測で埋めたセルは無く、言語モデルも使っていない。読めなかったセルは NULL。PDF は再配布していないので、確かめるには `pdf_url` から局のサイトの PDF を読む。

配布者の検証: 4,007 件の PDF の 48,211 セルを、同じ PDF の `pdftotext -layout` の文字の中に探し、見つからなかったのは 218 セル (2 行に割れた管理番号)。無作為の 30 点 (seed 20261030) を PDF と手で突き合わせ、28 点で全てのセルが一致した。

## 気をつけること

- 点に表を付けられるのは pdf_unique の 3,997 点だけ:
  PDF を共有する点と、複数の記録を持つ PDF (様式を読めなかった 403 件を含む) では、どの記録がどの点かが分からない。
- ふりがなで伏せた名前:
  ふりがなが名前のセルに混ざった 469 件 (556 点、熊本、福岡、秋田、山形、鹿児島などに多い) は、名前の 3 セルが NULL。ほかのセルは公開されている。
- 冠水実績のラベルとしての強さ:
  備考と北陸の欄から読める冠水の実績は、局ごとの書き方で決まる。ある箇所に書かれていないことは、冠水が無かったことを意味しない (下の実測)。北陸の「1m以上の冠水の有無」が過去の実績か想定かは、様式からは読み取れない (未確認)。
- 管理番号は読み取りの崩れを含みうる:
  結合は `pdf_key` で行う。

## 補足の実測 (2026-10-31、DuckDB 1.5.5 以上、固定した版から)

| 項目 | 値 |
|---|---|
| 行 | pdf_records 4,410 (pdf_key 一意)、point_pdf 4,525。様式と状態の内訳、pdf_match、name_cells の件数は README と一致 |
| セルの埋まり | 様式 A 3,369 件で 市町村 3,340、管理者 3,369、備考 968。様式 B 638 件で 道路名 638、備考 0 |
| 冠水の実績の手がかり (pdf_unique の 3,997 点) | 備考などに冠水実績、年、台風と冠水が書かれた点 248、北陸の 1m以上の冠水が「有」の点 149、どちらか 397。「冠水実績無」「冠水実績なし」「冠水解消」と書かれた点 9 (実績から除いた) |
| 実績の手がかりのある県 | 新潟 122 / 472、大阪 61 / 175、兵庫 45 / 160、福井 39 / 85、石川 27 / 111、滋賀 25 / 97、京都 24 / 107、鹿児島 18 / 144、奈良 15 / 50、熊本 14 / 155、和歌山 6 / 14、大分 1 / 31。ほかの 33 都府県は 0 (東京都も 0) |
| 関連設備の手がかり | 排水ポンプ 791 (北陸は「排水ポンプの有無」が有のもの)、警報・情報板などの表示 393、水位センサー 367 |
| 国のアンダーパスに付けると | 30 m 以内の冠水想定箇所が pdf_unique で読める国のアンダーパス 2,876 か所のうち、実績の手がかりあり 353 (12%)、排水ポンプ 697、水位センサー 363 |

手がかりは文字の正規表現で数えたもので、写真や地図は読んでいない。スクリプトと正規表現は `evals/curriculum/dry-runs/underpass-pilots/kansui_labels.py`。

## 出典の表示

点のデータセットと同じく、局ごとの出典と加工の記載が要る。文面は HF の README にある。
