---
kind: dataset
id: forest-typology-2020-v1
description: ForTy v1 の 2020 年基準の森林タイプ分類図、5 クラスの相対確信度、独立の検証標本。
url: https://api.figshare.com/v2/articles/32288616
license: CC BY 4.0。Figshare の 3 レコードと論文に記載。出典表示が必要
formats:
- ZIP 内の Cloud Optimized GeoTIFF
- 検証標本は CSV
crs: UTM 帯ごとに異なる。検証標本の位置列は緯度経度
spatial_coverage: 北緯 84 度から南緯 65 度の陸域
temporal_coverage: 2020 年の基準図
as_of:
  checked: 2026-10-25
contents:
- 5 森林タイプの相対確信度と残余の Other クラス
- 6 クラスに分類した派生図
- 検証標本の地点、専門家ラベル、合意ラベル、モデルの値
tables:
- name: relative_scores
  read: https://api.figshare.com/v2/articles/32288616
  grain: 10 m の推定画素。613 個の UTM ゾーン別 ZIP に分割
  rows: null
  id: []
- name: classification
  read: https://api.figshare.com/v2/articles/32301177
  grain: 10 m の 6 クラス分類画素。613 個の ZIP に分割
  rows: null
  id: []
- name: validation_sites
  read: https://api.figshare.com/v2/articles/33093404
  grain: 1 行が検証地点
  rows: 9100
  id:
  - sampleid
  columns:
  - name: sampleid
    type: 未確認
    meaning: 検証地点の識別子
  - name: lat
    type: 未確認
    meaning: 緯度
  - name: lon
    type: 未確認
    meaning: 経度
---

# ForTy 森林タイプ 2020 v1

## 出典、規模、API、許諾

- [原著論文](https://www.nature.com/articles/s41597-026-08299-5)は、Google DeepMind、Google Research、WRI、IIASA などによる全球 10 m の 2020 年基準図とする。主図は原生林、自然再生林、植林地、プランテーション、樹木作物・アグロフォレストリー、その他を区別する。5 バンドは相対的な確信度で、校正された事後確率とは限らない。
- 2026-10-25 に Figshare の公開 API を匿名で取得した。[相対確信度図](https://api.figshare.com/v2/articles/32288616)は 613 ZIP、合計 331,503,524,295 バイト。[分類図](https://api.figshare.com/v2/articles/32301177)は 613 ZIP、合計 25,648,189,902 バイト。どちらも CC BY 4.0。ZIP の内部 COG の個数、画素数、NoData は未実読。
- [検証標本](https://api.figshare.com/v2/articles/33093404)は 921,504 バイトの CSV。公開ダウンロード URL から実読し、ヘッダーと 9,100 データ行を数えた。合意ラベルがある地点は原著によると 8,190 件で、残りを自動的に正解として使わない。
- [Google Earth Engine カタログ](https://developers.google.com/earth-engine/datasets/catalog/projects_nature-trace_assets_forest_typology_forest_typology_2020_v1_0_collection)でも参照できる。ただし GEE の利用条件と認証は Figshare の匿名 API とは別。GNW Horizon での表示予定と、現時点の独立した配布元での取得を区別する。

## Hugging Face への凍結

CC BY 4.0 でライセンス上は候補。分類図だけでも約 25.65 GB、相対確信度図は約 331.50 GB なので、全量複製の前に利用者が必要とする範囲、出典表示、版、元の MD5、ファイル構成を検討する。現時点では凍結していない。

## 利用上の注意

2020 年の分類図を、別の年の森林損失と組み合わせる場合、基準年と変化年を混同しない。相対確信度の最大クラスを取った分類結果だけで不確実性を消さない。地点単位の判断には、現地確認または独立した高解像度画像による検証が要る。
