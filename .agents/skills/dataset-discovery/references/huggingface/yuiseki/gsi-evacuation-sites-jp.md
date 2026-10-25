---
kind: dataset
id: yuiseki/gsi-evacuation-sites-jp
description: 国土地理院が配る、全国の指定緊急避難場所と指定避難所の点。市町村が登録して公開に同意したもの。GeoParquet。
url: https://huggingface.co/datasets/yuiseki/gsi-evacuation-sites-jp
card_revision: d8ad2169789b71c951e8808b2e54a953030aae07
license: 国土地理院コンテンツ利用規約 (公共データ利用規約 1.0、CC BY 4.0 互換)。出典の表示と、加工したことの明示。国土地理院の注意事項を、使う相手に正確に伝える
formats:
- GeoParquet
- CSV
- GeoJSON
crs: OGC:CRS84
spatial_coverage: 日本全国。ただし公開していない市町村がある (sites は 1,699 市町村、shelters は 1,718 市町村)
temporal_coverage: 2026-10-06 (UTC) に取得した 1 時点。配布元は毎朝上書きし、版の番号を持たない
as_of:
  fetched: 2026-10-06
  source_last_update: 2026-10-05
contents:
- 指定緊急避難場所の点と、災害の種類ごとの指定
- 指定避難所の点と、福祉避難所の区別
tables:
- name: sites
  read: hf://datasets/yuiseki/gsi-evacuation-sites-jp@d8ad2169789b71c951e8808b2e54a953030aae07/parquet/sites.parquet
  grain: 1 つの指定緊急避難場所 (命を守るために、まず逃げる場所)
  rows: 115872
  id:
  - common_id
  join_keys:
  - column: common_id
    type: VARCHAR
    meaning: 全国共通の ID。E、市町村コード 5 桁、施設コード 5 桁、種別 2 桁 (20 が避難場所)、連番 1 桁。2 文字目から 5 文字が市町村コード
    joins:
    - jp-admin-2026-09:municipalities.code5 (substr(common_id, 2, 5) で取り出す)
    cast: 政令指定都市は区でなく市のコード (01100 など)。jp-admin-2026-09 の ward が空の、親の市の行と一致する
  no_key:
  - name: osm_id
    note: OpenStreetMap とは ID で結べない
  columns:
  - name: municipality
    type: VARCHAR
    meaning: 都道府県名と市町村名をつないだ文字列 (北海道札幌市)
  - name: earthquake
    type: BOOLEAN
    meaning: 地震に指定されているか。flood、landslide、storm_surge、tsunami、large_fire、inland_flooding、volcanic も同じ形。指定の無い災害には使えない
  - name: geometry
    type: GEOMETRY('OGC:CRS84')
    meaning: 経度と緯度の点。latitude、longitude の列と同じ値
- name: shelters
  read: hf://datasets/yuiseki/gsi-evacuation-sites-jp/parquet/shelters.parquet
  grain: 1 つの指定避難所 (危険が去るまで過ごす場所)
  rows: 83391
  id:
  - common_id
  join_keys:
  - column: common_id
    type: VARCHAR
    meaning: sites と同じ形。種別の 2 桁が 11 なら一般の避難所、12 なら福祉避難所
    joins:
    - jp-admin-2026-09:municipalities.code5 (substr(common_id, 2, 5) で取り出す)
  columns:
  - name: same_address_as_site
    type: BOOLEAN
    meaning: 同じ住所に指定緊急避難場所があるか
---

# 指定緊急避難場所と指定避難所 (gsi-evacuation-sites-jp)

国土地理院が配る、全国の指定緊急避難場所 (`sites`) と指定避難所 (`shelters`) の点。市町村長が指定し、市町村が登録して公開に同意したもの。2 つは別のもの: 避難場所は、災害が迫ったときにまず命を守るために逃げる場所で、災害の種類ごとに指定される。避難所は、危険が去るまで過ごす場所。国土地理院は「災害発生時には、指定避難所ではなく、指定緊急避難場所へ避難してください」と書いている。

## どこから読むか

Hugging Face の `yuiseki/gsi-evacuation-sites-jp`。Parquet は 2 つで、合わせて約 10 MB。

```
hf://datasets/yuiseki/gsi-evacuation-sites-jp/parquet/sites.parquet
hf://datasets/yuiseki/gsi-evacuation-sites-jp/parquet/shelters.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/gsi-evacuation-sites-jp>
- 配布元: <https://www.gsi.go.jp/bousaichiri/hinanbasho.html>
- 元の CSV と GeoJSON は `raw/2026-10-05/` にある。

## 中身

2026-10-14 に実測した (DuckDB 1.5.6)。

| 表 | 行数 | `common_id` の種類 | 市町村 | 座標の欠け | 日本の外の座標 |
|---|---:|---:|---:|---:|---:|
| `sites` | 115,872 | 115,872 | 1,699 | 0 | 0 |
| `shelters` | 83,391 | 83,391 | 1,718 | 0 | 0 |

| 項目 | 値 |
|---|---|
| 座標系 | `geometry` は `GEOMETRY('OGC:CRS84')`。配布元は測地系を書いていない。日本の JGD2011 と WGS 84 の差は 1 m よりずっと小さい |
| 時点 | 配布元は市町村の登録を毎朝上書きする。版の番号は無い。この凍結版は 2026-10-06 の取得 |
| ライセンス | 公共データ利用規約 1.0 (CC BY 4.0 互換)。出典は「国土地理院ウェブサイト」、加工したら加工したと書く |

## 気をつけること

- 避難場所と避難所を混ぜない。数を比べる、最寄りまでの距離を測る、といった分析では、どちらを使うかを問いの言葉から決める。
- 避難場所は災害の種類ごとの指定。「津波の避難場所」なら `tsunami` で絞る。全部を数えると、その災害に使えない場所を数える。
- 公開していない市町村がある。カードによれば、配布元の 1,747 市町村のうち 21 は何も公開していない (北方領土の 6 村を含む)。避難場所が 0 の市町村は、「無い」でなく「登録が無い」かもしれない。
- 点と市町村のコードは、必ずしも一致しない。`sites` の点を `jp-admin-2026-09` の市区町村の面 (ward が空の行) に空間結合すると、115,607 件は `common_id` の市町村の面に入り、219 件は別の市町村の面にだけ入り、46 件はどの面にも入らなかった (2026-10-14。面は海を含まないので、海岸の点が外れる)。市町村ごとに数えるなら、コードで数えるか面で数えるかを決め、違いを書く。
- 政令指定都市は市のコードで登録されている。区ごとに数えるなら、点を区の面に空間結合する。浜松市 (417 件、2026-10-15) は、2024 年 1 月に区が再編され、jp-admin-2026-09 の新しい 3 区には面が無いので、区ごとには数えられない。
- 同じ座標の避難場所の組が 136 ある (同じ施設の別の場所の登録など)。点の密度を数えるときは、重なりを数に入れるかを決める。
- 配布元の注意事項 (最新でない場合や未掲載の場合がある、など) を、使う相手に正確に伝える。

## ほかのデータとの結合

- 市町村: `substr(common_id, 2, 5)` が `jp-admin-2026-09` の `code5`。2026-10-14 に、`sites` の 1,699 と `shelters` の 1,718 の市町村コードが、全て `jp-admin-2026-09` にあった。区のコードの行はない。
- 人口: 市町村の人口は `jp-admin-2026-09`、格子の人口は `worldpop/japan.md` か国勢調査のメッシュ (`estat-census-mesh-2020.md`)。避難場所までの距離を人口で重み付けする、といった問いに使う。
